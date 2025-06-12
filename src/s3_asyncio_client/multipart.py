"""Multipart upload functionality for large objects."""

import xml.etree.ElementTree as ET
from typing import Any

from .exceptions import S3ClientError


class MultipartUpload:
    """Handles multipart upload operations."""

    def __init__(self, client, bucket: str, key: str, upload_id: str):
        self.client = client
        self.bucket = bucket
        self.key = key
        self.upload_id = upload_id
        self.parts: list[dict[str, Any]] = []

    async def upload_part(self, part_number: int, data: bytes) -> dict[str, Any]:
        """Upload a single part of the multipart upload.

        Args:
            part_number: Part number (1-based)
            data: Part data as bytes

        Returns:
            Dictionary with part information
        """
        if part_number < 1 or part_number > 10000:
            raise S3ClientError("Part number must be between 1 and 10000")

        params = {
            "partNumber": str(part_number),
            "uploadId": self.upload_id,
        }

        headers = {"Content-Length": str(len(data))}

        response = await self.client._make_request(
            method="PUT",
            bucket=self.bucket,
            key=self.key,
            headers=headers,
            params=params,
            data=data,
        )

        etag = response.headers.get("ETag", "").strip('"')
        response.close()

        part_info = {
            "part_number": part_number,
            "etag": etag,
            "size": len(data),
        }

        # Add to parts list (keep sorted by part number)
        self.parts = [p for p in self.parts if p["part_number"] != part_number]
        self.parts.append(part_info)
        self.parts.sort(key=lambda x: x["part_number"])

        return part_info

    async def complete(self) -> dict[str, Any]:
        """Complete the multipart upload.

        Returns:
            Dictionary with upload completion information
        """
        if not self.parts:
            raise S3ClientError("No parts uploaded")

        # Create the XML payload for completion
        parts_xml = []
        for part in self.parts:
            parts_xml.append(
                f"<Part>"
                f"<PartNumber>{part['part_number']}</PartNumber>"
                f'<ETag>"{part["etag"]}"</ETag>'
                f"</Part>"
            )

        xml_data = (
            "<CompleteMultipartUpload>"
            + "".join(parts_xml)
            + "</CompleteMultipartUpload>"
        )

        params = {"uploadId": self.upload_id}
        headers = {
            "Content-Type": "application/xml",
            "Content-Length": str(len(xml_data.encode())),
        }

        response = await self.client._make_request(
            method="POST",
            bucket=self.bucket,
            key=self.key,
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

        result = {
            "location": location.text if location is not None else None,
            "etag": etag.text.strip('"') if etag is not None else "",
            "bucket": self.bucket,
            "key": self.key,
            "parts_count": len(self.parts),
        }

        return result

    async def abort(self) -> None:
        """Abort the multipart upload."""
        params = {"uploadId": self.upload_id}

        await self.client._make_request(
            method="DELETE",
            bucket=self.bucket,
            key=self.key,
            params=params,
        )

        # Clear parts list
        self.parts.clear()
