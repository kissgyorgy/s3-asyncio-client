"""Asyncio-based multipart upload functionality for S3.

Based on s3transfer library architecture but implemented with pure asyncio.
Uses functions and coroutines instead of complex class hierarchies.
"""

import asyncio
import math
import xml.etree.ElementTree as ET
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .exceptions import S3ClientError

# S3 Constants (based on s3transfer)
MB = 1024 * 1024
GB = 1024 * MB

# S3 Limits
MIN_PART_SIZE = 5 * MB  # Minimum part size (5MB)
MAX_PART_SIZE = 5 * GB  # Maximum part size (5GB)
MAX_PARTS = 10000  # Maximum number of parts
MAX_SINGLE_UPLOAD_SIZE = 5 * GB  # Maximum single upload size

# Default configuration values (matching s3transfer defaults)
DEFAULT_MULTIPART_THRESHOLD = 8 * MB  # When to use multipart
DEFAULT_MULTIPART_CHUNKSIZE = 8 * MB  # Default part size
DEFAULT_MAX_CONCURRENCY = 10  # Max concurrent part uploads


@dataclass
class TransferConfig:
    """Configuration for multipart uploads."""

    multipart_threshold: int = DEFAULT_MULTIPART_THRESHOLD
    multipart_chunksize: int = DEFAULT_MULTIPART_CHUNKSIZE
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY


def should_use_multipart(file_size: int, threshold: int) -> bool:
    """Determine if multipart upload should be used.

    Args:
        file_size: Size of the file in bytes
        threshold: Threshold size for multipart uploads

    Returns:
        True if multipart upload should be used
    """
    return file_size > threshold


def adjust_chunk_size(current_chunksize: int, file_size: int | None = None) -> int:
    """Adjust chunk size to comply with S3 limits.

    Based on s3transfer's ChunksizeAdjuster logic.

    Args:
        current_chunksize: Currently configured chunk size
        file_size: Size of file being uploaded (optional)

    Returns:
        Adjusted chunk size that meets S3 requirements
    """
    chunksize = current_chunksize

    # Adjust for file size to ensure we don't exceed max parts
    if file_size is not None:
        chunksize = _adjust_for_max_parts(chunksize, file_size)

    # Ensure chunk size is within S3 limits
    return _adjust_for_size_limits(chunksize)


def _adjust_for_max_parts(chunksize: int, file_size: int) -> int:
    """Adjust chunk size to ensure we don't exceed MAX_PARTS."""
    num_parts = math.ceil(file_size / chunksize)

    while num_parts > MAX_PARTS:
        chunksize *= 2
        num_parts = math.ceil(file_size / chunksize)

    return chunksize


def _adjust_for_size_limits(chunksize: int) -> int:
    """Ensure chunk size is within S3 size limits."""
    if chunksize > MAX_PART_SIZE:
        return MAX_PART_SIZE
    elif chunksize < MIN_PART_SIZE:
        return MIN_PART_SIZE
    else:
        return chunksize


async def read_file_chunks(
    file_path: str | Path, part_size: int
) -> AsyncGenerator[bytes, None]:
    """Async generator that yields file chunks for multipart upload.

    Args:
        file_path: Path to the file to read
        part_size: Size of each chunk in bytes

    Yields:
        Chunks of file data
    """
    file_path = Path(file_path)

    def read_chunk():
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(part_size)
                if not chunk:
                    break
                yield chunk

    # Use asyncio to make file reading non-blocking

    for chunk in read_chunk():
        # Yield control to allow other coroutines to run
        await asyncio.sleep(0)
        yield chunk


async def read_fileobj_chunks(fileobj, part_size: int) -> AsyncGenerator[bytes, None]:
    """Async generator that yields chunks from a file-like object.

    Args:
        fileobj: File-like object to read from
        part_size: Size of each chunk in bytes

    Yields:
        Chunks of file data
    """
    while True:
        # Use asyncio to make reading non-blocking
        loop = asyncio.get_event_loop()
        chunk = await loop.run_in_executor(None, fileobj.read, part_size)

        if not chunk:
            break

        yield chunk


def calculate_file_size(file_source: str | Path | Any) -> int:
    """Calculate the size of the file source.

    Args:
        file_source: File path, Path object, or file-like object

    Returns:
        File size in bytes

    Raises:
        S3ClientError: If size cannot be determined
    """
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
    """Create a multipart upload and return upload ID.

    Args:
        client: S3Client instance
        bucket: S3 bucket name
        key: Object key
        content_type: MIME type of the object
        metadata: Custom metadata headers
        **extra_args: Additional arguments for the request

    Returns:
        Upload ID for the multipart upload
    """
    headers = {}

    # Set content type
    if content_type:
        headers["Content-Type"] = content_type

    # Add metadata headers
    if metadata:
        for key_name, value in metadata.items():
            headers[f"x-amz-meta-{key_name}"] = value

    # Add any extra arguments to headers
    headers.update(extra_args)

    params = {"uploads": ""}

    response = await client._make_request(
        method="POST",
        bucket=bucket,
        key=key,
        headers=headers,
        params=params,
    )

    # Parse response to get upload ID
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
    """Upload a single part of a multipart upload.

    Args:
        client: S3Client instance
        bucket: S3 bucket name
        key: Object key
        upload_id: Multipart upload ID
        part_number: Part number (1-based)
        data: Part data as bytes
        **extra_args: Additional arguments for the request

    Returns:
        Dictionary with part information (part_number, etag, size)
    """
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
    """Complete a multipart upload.

    Args:
        client: S3Client instance
        bucket: S3 bucket name
        key: Object key
        upload_id: Multipart upload ID
        parts: List of part dictionaries with part_number and etag
        **extra_args: Additional arguments for the request

    Returns:
        Dictionary with completion information
    """
    if not parts:
        raise S3ClientError("No parts to complete")

    # Sort parts by part number to ensure correct order
    parts_sorted = sorted(parts, key=lambda x: x["part_number"])

    # Create the XML payload for completion
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

    # Parse response
    response_text = await response.text()
    response.close()
    root = ET.fromstring(response_text)

    # Extract completion information
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
    """Abort a multipart upload.

    Args:
        client: S3Client instance
        bucket: S3 bucket name
        key: Object key
        upload_id: Multipart upload ID
        **extra_args: Additional arguments for the request
    """
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
    """Upload a file using either single-part or multipart upload.

    Automatically determines whether to use multipart upload based on file size
    and configuration. Uses asyncio.TaskGroup for concurrent part uploads.

    Args:
        client: S3Client instance
        bucket: S3 bucket name
        key: Object key
        file_source: File path, Path object, or file-like object
        config: Transfer configuration (optional)
        content_type: MIME type of the object
        metadata: Custom metadata headers
        progress_callback: Function called with (bytes_transferred) for progress
        **extra_args: Additional arguments for the request

    Returns:
        Dictionary with upload result information
    """
    if config is None:
        config = TransferConfig()

    # Determine file size
    file_size = calculate_file_size(file_source)

    # Decide upload strategy
    if not should_use_multipart(file_size, config.multipart_threshold):
        # Use single-part upload via existing put_object method
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
        # Use multipart upload
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
    """Handle single-part upload using existing put_object method."""
    # Read file data
    if isinstance(file_source, str | Path):
        with open(file_source, "rb") as f:
            data = f.read()
    else:
        # File-like object
        data = file_source.read()

    # Call progress callback if provided
    if progress_callback:
        progress_callback(len(data))

    # Use existing put_object method
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
    """Handle multipart upload with concurrent part uploads."""
    # Calculate optimal part size
    part_size = adjust_chunk_size(config.multipart_chunksize, file_size)

    # Create multipart upload
    upload_id = await create_multipart_upload(
        client, bucket, key, content_type, metadata, **extra_args
    )

    try:
        # Collect all parts and upload concurrently
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

        # Complete multipart upload
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
        # Abort upload on any error
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
    """Upload all parts concurrently using asyncio.TaskGroup."""

    # Choose appropriate chunk reader based on file source type
    if isinstance(file_source, str | Path):
        chunk_generator = read_file_chunks(file_source, part_size)
    else:
        chunk_generator = read_fileobj_chunks(file_source, part_size)

    # Collect all chunks first to enable concurrent upload
    chunks = []
    part_number = 1

    async for chunk in chunk_generator:
        chunks.append((part_number, chunk))
        part_number += 1

    # Create semaphore to limit concurrency
    semaphore = asyncio.Semaphore(max_concurrency)

    async def upload_single_part(part_num: int, data: bytes) -> dict[str, Any]:
        """Upload a single part with concurrency control."""
        async with semaphore:
            result = await upload_part(
                client, bucket, key, upload_id, part_num, data, **extra_args
            )

            # Call progress callback if provided
            if progress_callback:
                progress_callback(len(data))

            return result

    # Upload all parts concurrently using TaskGroup
    async with asyncio.TaskGroup() as tg:
        tasks = [
            tg.create_task(upload_single_part(part_num, data))
            for part_num, data in chunks
        ]

    # Collect results from all tasks
    parts = [task.result() for task in tasks]

    return parts
