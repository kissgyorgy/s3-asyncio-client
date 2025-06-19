from typing import Any

from .base import _S3ClientBase


class _ObjectOperations(_S3ClientBase):
    async def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = {}

        if content_type:
            headers["Content-Type"] = content_type

        if metadata:
            for key_name, value in metadata.items():
                headers[f"x-amz-meta-{key_name}"] = value

        headers["Content-Length"] = str(len(data))

        response = await self._make_request("PUT", key=key, headers=headers, data=data)

        result = {
            "etag": response.headers.get("ETag", "").strip('"'),
            "version_id": response.headers.get("x-amz-version-id"),
            "server_side_encryption": response.headers.get(
                "x-amz-server-side-encryption"
            ),
        }

        response.close()
        return result

    async def get_object(self, key: str) -> dict[str, Any]:
        response = await self._make_request("GET", key=key)

        body = await response.read()
        response.close()

        metadata = {}
        for header_name, header_value in response.headers.items():
            if header_name.lower().startswith("x-amz-meta-"):
                # Remove the x-amz-meta- prefix
                meta_key = header_name[11:]
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

    async def head_object(self, key: str) -> dict[str, Any]:
        """Get object metadata without downloading the object."""
        response = await self._make_request("HEAD", key=key)

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

    async def delete_object(self, key: str) -> dict[str, Any]:
        response = await self._make_request("DELETE", key=key)
        result = {
            "delete_marker": response.headers.get("x-amz-delete-marker") == "true",
            "version_id": response.headers.get("x-amz-version-id"),
        }
        response.close()
        return result

    def generate_presigned_url(
        self,
        method: str,
        key: str,
        expires_in: int = 3600,
        params: dict[str, str] | None = None,
    ) -> str:
        url = self.bucket_url / key
        return self._auth.create_presigned_url(method, url, expires_in, params)
