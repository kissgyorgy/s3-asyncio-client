"""Asyncio-based multipart upload functionality for S3.

Based on s3transfer library architecture but implemented with asyncio.
Uses functions and coroutines instead of complex class hierarchies and threads.
"""

import asyncio
import math
import xml.etree.ElementTree as ET
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .exceptions import S3ClientError

# constants based on s3transfer
MB = 1024 * 1024
GB = 1024 * MB

# S3 Limits
MIN_PART_SIZE = 5 * MB
MAX_PART_SIZE = 5 * GB
MAX_PARTS = 10_000
MAX_SINGLE_UPLOAD_SIZE = 5 * GB

# Default configuration values (matching s3transfer defaults)
DEFAULT_MULTIPART_THRESHOLD = 8 * MB
DEFAULT_MULTIPART_CHUNKSIZE = 8 * MB
DEFAULT_MAX_CONCURRENCY = 10


@dataclass
class TransferConfig:
    multipart_threshold: int = DEFAULT_MULTIPART_THRESHOLD
    multipart_chunksize: int = DEFAULT_MULTIPART_CHUNKSIZE
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY


def should_use_multipart(file_size: int, threshold: int) -> bool:
    return file_size > threshold


def adjust_chunk_size(current_chunksize: int, file_size: int | None = None) -> int:
    """Adjust chunk size to comply with S3 limits.
    Based on s3transfer's ChunksizeAdjuster logic.
    """
    chunksize = current_chunksize

    if file_size is not None:
        chunksize = _adjust_for_max_parts(chunksize, file_size)

    return _adjust_for_size_limits(chunksize)


def _adjust_for_max_parts(chunksize: int, file_size: int) -> int:
    num_parts = math.ceil(file_size / chunksize)

    while num_parts > MAX_PARTS:
        chunksize *= 2
        num_parts = math.ceil(file_size / chunksize)

    return chunksize


def _adjust_for_size_limits(chunksize: int) -> int:
    if chunksize > MAX_PART_SIZE:
        return MAX_PART_SIZE
    elif chunksize < MIN_PART_SIZE:
        return MIN_PART_SIZE
    else:
        return chunksize


async def read_file_chunks(
    file_path: str | Path, part_size: int
) -> AsyncGenerator[bytes, None]:
    """Async generator that yields file chunks for multipart upload."""
    file_path = Path(file_path)

    def read_chunk():
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(part_size)
                if not chunk:
                    break
                yield chunk

    # TODO: Use asyncio to make file reading non-blocking

    for chunk in read_chunk():
        await asyncio.sleep(0)
        yield chunk


async def read_fileobj_chunks(fileobj, part_size: int) -> AsyncGenerator[bytes, None]:
    """Async generator that yields chunks from a file-like object."""
    while True:
        # Use asyncio to make reading non-blocking
        loop = asyncio.get_event_loop()
        chunk = await loop.run_in_executor(None, fileobj.read, part_size)

        if not chunk:
            break

        yield chunk


def calculate_file_size(file_source: str | Path | Any) -> int:
    if isinstance(file_source, str | Path):
        try:
            return Path(file_source).stat().st_size
        except (OSError, FileNotFoundError) as e:
            raise S3ClientError(
                f"Cannot determine size of file source: {file_source} - {e}"
            ) from e
    elif hasattr(file_source, "seek") and hasattr(file_source, "tell"):
        # File-like object with seek/tell
        current_pos = file_source.tell()
        file_source.seek(0, 2)  # Seek to end
        size = file_source.tell()
        file_source.seek(current_pos)  # Restore position
        return size
    else:
        raise S3ClientError(
            f"Cannot determine size of file source: {type(file_source)}"
        )


# Core multipart S3 operations
async def create_multipart_upload(
    client,
    bucket: str,
    key: str,
    content_type: str | None = None,
    metadata: dict[str, str] | None = None,
    **extra_args,
) -> str:
    """Create a multipart upload and return the upload ID."""
    headers = {}

    if content_type:
        headers["Content-Type"] = content_type

    if metadata:
        for key_name, value in metadata.items():
            headers[f"x-amz-meta-{key_name}"] = value

    headers.update(extra_args)

    params = {"uploads": ""}

    response = await client._make_request(
        method="POST",
        bucket=bucket,
        key=key,
        headers=headers,
        params=params,
    )

    response_text = await response.text()
    response.close()
    root = ET.fromstring(response_text)

    # Try to find UploadId with namespace first, then without
    upload_id_elem = root.find(".//{http://s3.amazonaws.com/doc/2006-03-01/}UploadId")
    if upload_id_elem is None:
        upload_id_elem = root.find(".//UploadId")
    if upload_id_elem is None:
        raise S3ClientError("No UploadId in response")

    return upload_id_elem.text


async def upload_part(
    client,
    bucket: str,
    key: str,
    upload_id: str,
    part_number: int,
    data: bytes,
    **extra_args,
) -> dict[str, Any]:
    """Upload a single part of a multipart upload."""
    if part_number < 1 or part_number > MAX_PARTS:
        raise S3ClientError(f"Part number must be between 1 and {MAX_PARTS}")

    params = {
        "partNumber": str(part_number),
        "uploadId": upload_id,
    }

    headers = {"Content-Length": str(len(data))}
    headers.update(extra_args)

    response = await client._make_request(
        method="PUT",
        bucket=bucket,
        key=key,
        headers=headers,
        params=params,
        data=data,
    )

    etag = response.headers.get("ETag", "").strip('"')
    response.close()

    return {
        "part_number": part_number,
        "etag": etag,
        "size": len(data),
    }


async def complete_multipart_upload(
    client,
    bucket: str,
    key: str,
    upload_id: str,
    parts: list[dict[str, Any]],
    **extra_args,
) -> dict[str, Any]:
    if not parts:
        raise S3ClientError("No parts to complete")

    parts_sorted = sorted(parts, key=lambda x: x["part_number"])

    parts_xml = []
    for part in parts_sorted:
        parts_xml.append(
            f"<Part>"
            f"<PartNumber>{part['part_number']}</PartNumber>"
            f'<ETag>"{part["etag"]}"</ETag>'
            f"</Part>"
        )

    xml_data = (
        "<CompleteMultipartUpload>" + "".join(parts_xml) + "</CompleteMultipartUpload>"
    )

    params = {"uploadId": upload_id}
    headers = {
        "Content-Type": "application/xml",
        "Content-Length": str(len(xml_data.encode())),
    }
    headers.update(extra_args)

    response = await client._make_request(
        method="POST",
        bucket=bucket,
        key=key,
        headers=headers,
        params=params,
        data=xml_data.encode(),
    )

    response_text = await response.text()
    response.close()
    root = ET.fromstring(response_text)

    location = root.find("Location")
    etag = root.find("ETag")

    return {
        "location": location.text if location is not None else None,
        "etag": etag.text.strip('"') if etag is not None else "",
        "bucket": bucket,
        "key": key,
        "parts_count": len(parts_sorted),
    }


async def abort_multipart_upload(
    client, bucket: str, key: str, upload_id: str, **extra_args
) -> None:
    params = {"uploadId": upload_id}
    headers = {}
    headers.update(extra_args)

    response = await client._make_request(
        method="DELETE",
        bucket=bucket,
        key=key,
        headers=headers,
        params=params,
    )
    response.close()


# Main upload orchestrator
async def upload_file(
    client,
    bucket: str,
    key: str,
    file_source: str | Path | Any,
    config: TransferConfig | None = None,
    content_type: str | None = None,
    metadata: dict[str, str] | None = None,
    progress_callback: Callable | None = None,
    **extra_args,
) -> dict[str, Any]:
    if config is None:
        config = TransferConfig()

    file_size = calculate_file_size(file_source)

    if not should_use_multipart(file_size, config.multipart_threshold):
        return await _upload_single_part(
            client,
            bucket,
            key,
            file_source,
            content_type,
            metadata,
            progress_callback,
            **extra_args,
        )
    else:
        return await _upload_multipart(
            client,
            bucket,
            key,
            file_source,
            file_size,
            config,
            content_type,
            metadata,
            progress_callback,
            **extra_args,
        )


async def _upload_single_part(
    client,
    bucket: str,
    key: str,
    file_source: str | Path | Any,
    content_type: str | None,
    metadata: dict[str, str] | None,
    progress_callback: Callable | None,
    **extra_args,
) -> dict[str, Any]:
    if isinstance(file_source, str | Path):
        with open(file_source, "rb") as f:
            data = f.read()
    else:
        data = file_source.read()

    if progress_callback:
        progress_callback(len(data))

    result = await client.put_object(
        bucket=bucket,
        key=key,
        data=data,
        content_type=content_type,
        metadata=metadata,
        **extra_args,
    )

    return {
        "etag": result.get("etag", ""),
        "bucket": bucket,
        "key": key,
        "size": len(data),
        "upload_type": "single_part",
    }


async def _upload_multipart(
    client,
    bucket: str,
    key: str,
    file_source: str | Path | Any,
    file_size: int,
    config: TransferConfig,
    content_type: str | None,
    metadata: dict[str, str] | None,
    progress_callback: Callable | None,
    **extra_args,
) -> dict[str, Any]:
    part_size = adjust_chunk_size(config.multipart_chunksize, file_size)

    upload_id = await create_multipart_upload(
        client, bucket, key, content_type, metadata, **extra_args
    )

    try:
        parts = await _upload_parts_concurrently(
            client,
            bucket,
            key,
            upload_id,
            file_source,
            part_size,
            config.max_concurrency,
            progress_callback,
            **extra_args,
        )

        result = await complete_multipart_upload(
            client, bucket, key, upload_id, parts, **extra_args
        )

        result.update(
            {
                "size": file_size,
                "upload_type": "multipart",
                "part_size": part_size,
            }
        )

        return result

    except Exception:
        try:
            await abort_multipart_upload(client, bucket, key, upload_id, **extra_args)
        except Exception:
            pass  # Ignore abort errors
        raise


async def _upload_parts_concurrently(
    client,
    bucket: str,
    key: str,
    upload_id: str,
    file_source: str | Path | Any,
    part_size: int,
    max_concurrency: int,
    progress_callback: Callable | None,
    **extra_args,
) -> list[dict[str, Any]]:
    if isinstance(file_source, str | Path):
        chunk_generator = read_file_chunks(file_source, part_size)
    else:
        chunk_generator = read_fileobj_chunks(file_source, part_size)

    chunks = []
    part_number = 1

    async for chunk in chunk_generator:
        chunks.append((part_number, chunk))
        part_number += 1

    semaphore = asyncio.Semaphore(max_concurrency)

    async def upload_single_part(part_num: int, data: bytes) -> dict[str, Any]:
        async with semaphore:
            result = await upload_part(
                client, bucket, key, upload_id, part_num, data, **extra_args
            )

            if progress_callback:
                progress_callback(len(data))

            return result

    async with asyncio.TaskGroup() as tg:
        tasks = [
            tg.create_task(upload_single_part(part_num, data))
            for part_num, data in chunks
        ]

    parts = [task.result() for task in tasks]

    return parts
