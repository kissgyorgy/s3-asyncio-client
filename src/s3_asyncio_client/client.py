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
        async with self._session.request(
            method=method,
            url=url,
            headers=signed_headers,
            params=params,
            data=data,
        ) as response:
            if response.status >= 400:
                error_text = await response.text()
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
        # Implementation will be added in next task
        raise NotImplementedError("put_object will be implemented next")

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
        # Implementation will be added in next task
        raise NotImplementedError("get_object will be implemented next")

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
        # Implementation will be added in next task
        raise NotImplementedError("head_object will be implemented next")

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
        # Implementation will be added in next task
        raise NotImplementedError("list_objects will be implemented next")

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
        # Implementation will be added in next task
        raise NotImplementedError("generate_presigned_url will be implemented next")
