"""Main S3 client implementation."""

import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

import aiohttp

from .auth import AWSSignatureV4
from .exceptions import (
    S3AccessDeniedError,
    S3ClientError,
    S3InvalidRequestError,
    S3NotFoundError,
    S3ServerError,
)
from .multipart import MultipartUpload


class S3Client:
    """Minimal asyncio S3 client."""

    def __init__(
        self,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
    ):
        """Initialize S3 client.

        Args:
            access_key: AWS access key ID
            secret_key: AWS secret access key
            region: AWS region (default: us-east-1)
            endpoint_url: Custom S3 endpoint URL (for S3-compatible services)
        """
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.endpoint_url = endpoint_url or f"https://s3.{region}.amazonaws.com"

        self._auth = AWSSignatureV4(access_key, secret_key, region)
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _ensure_session(self):
        """Ensure aiohttp session is created."""
        if self._session is None:
            self._session = aiohttp.ClientSession()

    async def close(self):
        """Close the client and cleanup resources."""
        if self._session:
            await self._session.close()
            self._session = None

    def _build_url(self, bucket: str, key: str | None = None) -> str:
        """Build S3 URL for bucket and key."""
        if key:
            # Virtual hosted-style URL: https://bucket.s3.region.amazonaws.com/key
            if self.endpoint_url.startswith("https://s3."):
                base_url = self.endpoint_url.replace("s3.", f"{bucket}.s3.")
                return f"{base_url}/{urllib.parse.quote(key, safe='/')}"
            else:
                # Path-style URL for custom endpoints
                quoted_key = urllib.parse.quote(key, safe="/")
                return f"{self.endpoint_url}/{bucket}/{quoted_key}"
        else:
            # Bucket-only URL
            if self.endpoint_url.startswith("https://s3."):
                return self.endpoint_url.replace("s3.", f"{bucket}.s3.")
            else:
                return f"{self.endpoint_url}/{bucket}"

    def _parse_error_response(self, status: int, response_text: str) -> Exception:
        """Parse S3 error response and return appropriate exception."""
        try:
            root = ET.fromstring(response_text)
            error_code = root.find("Code")
            message = root.find("Message")

            error_code_text = error_code.text if error_code is not None else "Unknown"
            message_text = message.text if message is not None else "Unknown error"

        except ET.ParseError:
            error_code_text = "Unknown"
            message_text = response_text or "Unknown error"

        # Map specific error codes to custom exceptions
        if status == 404 or error_code_text in ["NoSuchKey", "NoSuchBucket"]:
            return S3NotFoundError(message_text)
        elif status == 403 or error_code_text == "AccessDenied":
            return S3AccessDeniedError(message_text)
        elif error_code_text == "InvalidRequest":
            return S3InvalidRequestError(message_text)
        elif 400 <= status < 500:
            return S3ClientError(message_text, status, error_code_text)
        else:
            return S3ServerError(message_text, status, error_code_text)

    async def _make_request(
        self,
        method: str,
        bucket: str,
        key: str | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        data: bytes | None = None,
    ) -> aiohttp.ClientResponse:
        """Make authenticated HTTP request to S3."""
        await self._ensure_session()

        url = self._build_url(bucket, key)
        request_headers = headers.copy() if headers else {}

        # Sign the request
        signed_headers = self._auth.sign_request(
            method=method,
            url=url,
            headers=request_headers,
            payload=data or b"",
            query_params=params,
        )

        # Make the request
        response = await self._session.request(
            method=method,
            url=url,
            headers=signed_headers,
            params=params,
            data=data,
        )

        if response.status >= 400:
            error_text = await response.text()
            response.close()
            raise self._parse_error_response(response.status, error_text)

        return response

    async def put_object(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Upload an object to S3.

        Args:
            bucket: S3 bucket name
            key: Object key (path)
            data: Object data as bytes
            content_type: MIME type of the object
            metadata: Custom metadata headers (without x-amz-meta- prefix)

        Returns:
            Dictionary with upload response information
        """
        headers = {}

        # Set content type
        if content_type:
            headers["Content-Type"] = content_type

        # Add metadata headers
        if metadata:
            for key_name, value in metadata.items():
                headers[f"x-amz-meta-{key_name}"] = value

        # Set content length
        headers["Content-Length"] = str(len(data))

        response = await self._make_request(
            method="PUT",
            bucket=bucket,
            key=key,
            headers=headers,
            data=data,
        )

        # Extract response information
        result = {
            "etag": response.headers.get("ETag", "").strip('"'),
            "version_id": response.headers.get("x-amz-version-id"),
            "server_side_encryption": response.headers.get(
                "x-amz-server-side-encryption"
            ),
        }

        response.close()
        return result

    async def get_object(
        self,
        bucket: str,
        key: str,
    ) -> dict[str, Any]:
        """Download an object from S3.

        Args:
            bucket: S3 bucket name
            key: Object key (path)

        Returns:
            Dictionary with object data and metadata
        """
        response = await self._make_request(
            method="GET",
            bucket=bucket,
            key=key,
        )

        # Read the response body
        body = await response.read()
        response.close()

        # Extract metadata from headers
        metadata = {}
        for header_name, header_value in response.headers.items():
            if header_name.lower().startswith("x-amz-meta-"):
                # Remove the x-amz-meta- prefix
                meta_key = header_name[11:]  # len("x-amz-meta-") = 11
                metadata[meta_key] = header_value

        result = {
            "body": body,
            "content_type": response.headers.get("Content-Type"),
            "content_length": int(response.headers.get("Content-Length", 0)),
            "etag": response.headers.get("ETag", "").strip('"'),
            "last_modified": response.headers.get("Last-Modified"),
            "version_id": response.headers.get("x-amz-version-id"),
            "server_side_encryption": response.headers.get(
                "x-amz-server-side-encryption"
            ),
            "metadata": metadata,
        }

        return result

    async def head_object(
        self,
        bucket: str,
        key: str,
    ) -> dict[str, Any]:
        """Get object metadata without downloading the object.

        Args:
            bucket: S3 bucket name
            key: Object key (path)

        Returns:
            Dictionary with object metadata
        """
        response = await self._make_request(
            method="HEAD",
            bucket=bucket,
            key=key,
        )

        # Extract metadata from headers (same as get_object, but no body)
        metadata = {}
        for header_name, header_value in response.headers.items():
            if header_name.lower().startswith("x-amz-meta-"):
                # Remove the x-amz-meta- prefix
                meta_key = header_name[11:]  # len("x-amz-meta-") = 11
                metadata[meta_key] = header_value

        result = {
            "content_type": response.headers.get("Content-Type"),
            "content_length": int(response.headers.get("Content-Length", 0)),
            "etag": response.headers.get("ETag", "").strip('"'),
            "last_modified": response.headers.get("Last-Modified"),
            "version_id": response.headers.get("x-amz-version-id"),
            "server_side_encryption": response.headers.get(
                "x-amz-server-side-encryption"
            ),
            "metadata": metadata,
        }

        response.close()
        return result

    async def delete_object(
        self,
        bucket: str,
        key: str,
    ) -> dict[str, Any]:
        """Delete an object from S3.

        Args:
            bucket: S3 bucket name
            key: Object key (path)

        Returns:
            Dictionary with deletion information
        """
        response = await self._make_request(
            method="DELETE",
            bucket=bucket,
            key=key,
        )

        result = {
            "delete_marker": response.headers.get("x-amz-delete-marker") == "true",
            "version_id": response.headers.get("x-amz-version-id"),
        }

        response.close()
        return result

    async def create_bucket(
        self,
        bucket: str,
    ) -> dict[str, Any]:
        """Create a new S3 bucket.

        Args:
            bucket: S3 bucket name

        Returns:
            Dictionary with bucket creation information
        """
        response = await self._make_request(
            method="PUT",
            bucket=bucket,
        )

        result = {
            "location": response.headers.get("Location"),
        }

        response.close()
        return result

    async def list_objects(
        self,
        bucket: str,
        prefix: str | None = None,
        max_keys: int = 1000,
        continuation_token: str | None = None,
    ) -> dict[str, Any]:
        """List objects in a bucket.

        Args:
            bucket: S3 bucket name
            prefix: Object key prefix filter
            max_keys: Maximum number of objects to return
            continuation_token: Token for pagination

        Returns:
            Dictionary with list of objects and pagination info
        """
        # Build query parameters
        params = {
            "list-type": "2",  # Use ListObjectsV2
            "max-keys": str(max_keys),
        }

        if prefix:
            params["prefix"] = prefix

        if continuation_token:
            params["continuation-token"] = continuation_token

        response = await self._make_request(
            method="GET",
            bucket=bucket,
            params=params,
        )

        # Parse XML response
        response_text = await response.text()
        response.close()
        root = ET.fromstring(response_text)

        # Extract objects
        objects = []
        for content in root.findall(
            ".//{http://s3.amazonaws.com/doc/2006-03-01/}Contents"
        ):
            key = content.find(".//{http://s3.amazonaws.com/doc/2006-03-01/}Key")
            last_modified = content.find(
                ".//{http://s3.amazonaws.com/doc/2006-03-01/}LastModified"
            )
            etag = content.find(".//{http://s3.amazonaws.com/doc/2006-03-01/}ETag")
            size = content.find(".//{http://s3.amazonaws.com/doc/2006-03-01/}Size")
            storage_class = content.find(
                ".//{http://s3.amazonaws.com/doc/2006-03-01/}StorageClass"
            )

            obj = {
                "key": key.text if key is not None else "",
                "last_modified": (
                    last_modified.text if last_modified is not None else ""
                ),
                "etag": etag.text.strip('"') if etag is not None else "",
                "size": int(size.text) if size is not None else 0,
                "storage_class": (
                    storage_class.text if storage_class is not None else "STANDARD"
                ),
            }
            objects.append(obj)

        # Extract pagination info
        is_truncated_elem = root.find(
            ".//{http://s3.amazonaws.com/doc/2006-03-01/}IsTruncated"
        )
        next_token_elem = root.find(
            ".//{http://s3.amazonaws.com/doc/2006-03-01/}NextContinuationToken"
        )

        is_truncated = (
            is_truncated_elem is not None and is_truncated_elem.text == "true"
        )
        next_continuation_token = (
            next_token_elem.text if next_token_elem is not None else None
        )

        result = {
            "objects": objects,
            "is_truncated": is_truncated,
            "next_continuation_token": next_continuation_token,
            "prefix": prefix,
            "max_keys": max_keys,
        }

        return result

    def generate_presigned_url(
        self,
        method: str,
        bucket: str,
        key: str,
        expires_in: int = 3600,
        params: dict[str, str] | None = None,
    ) -> str:
        """Generate a presigned URL for S3 operations.

        Args:
            method: HTTP method (GET, PUT, etc.)
            bucket: S3 bucket name
            key: Object key (path)
            expires_in: URL expiration time in seconds
            params: Additional query parameters

        Returns:
            Presigned URL string
        """
        url = self._build_url(bucket, key)

        return self._auth.create_presigned_url(
            method=method,
            url=url,
            expires_in=expires_in,
            query_params=params,
        )

    async def create_multipart_upload(
        self,
        bucket: str,
        key: str,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> MultipartUpload:
        """Initiate a multipart upload.

        Args:
            bucket: S3 bucket name
            key: Object key (path)
            content_type: MIME type of the object
            metadata: Custom metadata headers (without x-amz-meta- prefix)

        Returns:
            MultipartUpload instance for managing the upload
        """
        headers = {}

        # Set content type
        if content_type:
            headers["Content-Type"] = content_type

        # Add metadata headers
        if metadata:
            for key_name, value in metadata.items():
                headers[f"x-amz-meta-{key_name}"] = value

        params = {"uploads": ""}

        response = await self._make_request(
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
        upload_id_elem = root.find(
            ".//{http://s3.amazonaws.com/doc/2006-03-01/}UploadId"
        )
        if upload_id_elem is None:
            upload_id_elem = root.find(".//UploadId")
        if upload_id_elem is None:
            raise S3ClientError("No UploadId in response")

        upload_id = upload_id_elem.text

        return MultipartUpload(self, bucket, key, upload_id)

    async def upload_file_multipart(
        self,
        bucket: str,
        key: str,
        data: bytes,
        part_size: int = 5 * 1024 * 1024,  # 5MB default
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Upload a large file using multipart upload.

        Args:
            bucket: S3 bucket name
            key: Object key (path)
            data: File data as bytes
            part_size: Size of each part in bytes (minimum 5MB except last part)
            content_type: MIME type of the object
            metadata: Custom metadata headers

        Returns:
            Dictionary with upload completion information
        """
        if part_size < 5 * 1024 * 1024:
            raise S3ClientError("Part size must be at least 5MB")

        if len(data) <= part_size:
            # For small files, use regular put_object
            return await self.put_object(
                bucket=bucket,
                key=key,
                data=data,
                content_type=content_type,
                metadata=metadata,
            )

        # Create multipart upload
        multipart = await self.create_multipart_upload(
            bucket=bucket,
            key=key,
            content_type=content_type,
            metadata=metadata,
        )

        try:
            # Upload parts
            part_number = 1
            offset = 0

            while offset < len(data):
                # Calculate part data
                end_offset = min(offset + part_size, len(data))
                part_data = data[offset:end_offset]

                # Upload part
                await multipart.upload_part(part_number, part_data)

                offset = end_offset
                part_number += 1

            # Complete upload
            result = await multipart.complete()
            return result

        except Exception:
            # Abort upload on any error
            try:
                await multipart.abort()
            except Exception:
                pass  # Ignore abort errors
            raise
