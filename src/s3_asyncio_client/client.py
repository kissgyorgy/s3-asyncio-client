import configparser
import os
import pathlib
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
    def __init__(
        self,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
    ):
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.endpoint_url = endpoint_url or f"https://s3.{region}.amazonaws.com"

        self._auth = AWSSignatureV4(access_key, secret_key, region)
        self._session: aiohttp.ClientSession | None = None

    @classmethod
    def from_aws_config(
        cls,
        profile_name: str = "default",
        config_path: str | pathlib.Path | None = None,
        credentials_path: str | pathlib.Path | None = None,
    ) -> "S3Client":
        if config_path is None:
            config_path = pathlib.Path.home() / ".aws" / "config"
        else:
            config_path = pathlib.Path(config_path)

        if credentials_path is not None:
            credentials_path = pathlib.Path(credentials_path)

        config = configparser.ConfigParser()
        credentials = configparser.ConfigParser()

        # Config file may or may not exist
        config_data = {}
        if config_path.exists():
            config.read(config_path)
            # Handle profile section names (AWS config uses "profile <name>" except for default)  # noqa: E501
            config_section = (
                profile_name if profile_name == "default" else f"profile {profile_name}"
            )
            if config_section in config:
                config_data = dict(config[config_section])

        # Load credentials from file if available
        credentials_data = {}
        if credentials_path and credentials_path.exists():
            credentials.read(credentials_path)
            if profile_name in credentials:
                credentials_data = dict(credentials[profile_name])

        # Extract required parameters (credentials takes precedence over config)
        access_key = credentials_data.get("aws_access_key_id") or config_data.get(
            "aws_access_key_id"
        )
        secret_key = credentials_data.get("aws_secret_access_key") or config_data.get(
            "aws_secret_access_key"
        )

        if not access_key:
            raise ValueError(
                f"aws_access_key_id not found for profile '{profile_name}' "
                f"in config or credentials files"
            )
        if not secret_key:
            raise ValueError(
                f"aws_secret_access_key not found for profile '{profile_name}' "
                f"in config or credentials files"
            )

        # Extract optional parameters (with fallbacks)
        region = (
            credentials_data.get("region")
            or config_data.get("region")
            or os.environ.get("AWS_DEFAULT_REGION")
            or "us-east-1"
        )

        endpoint_url = (
            credentials_data.get("endpoint_url")
            or config_data.get("endpoint_url")
            or None
        )

        s3_section = config_data.get("s3")
        if isinstance(s3_section, dict) and "endpoint_url" in s3_section:
            endpoint_url = endpoint_url or s3_section["endpoint_url"]

        return cls(
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            endpoint_url=endpoint_url,
        )

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _ensure_session(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    def _get_endpoint_bucket_name(self) -> str | None:
        from urllib.parse import urlparse

        parsed_url = urlparse(self.endpoint_url)
        if parsed_url.hostname:
            hostname_parts = parsed_url.hostname.split(".")
            # Check if this looks like a bucket-specific endpoint
            # (like DigitalOcean Spaces)
            # Must have at least 3 parts and not be standard S3
            if len(hostname_parts) >= 3 and not self.endpoint_url.startswith(
                "https://s3."
            ):
                return hostname_parts[0]
        return None

    def get_effective_bucket_name(self, bucket: str) -> str:
        endpoint_bucket = self._get_endpoint_bucket_name()
        return endpoint_bucket if endpoint_bucket else bucket

    def _build_url(self, bucket: str, key: str | None = None) -> str:
        endpoint_bucket = self._get_endpoint_bucket_name()

        if key:
            # Virtual hosted-style URL: https://bucket.s3.region.amazonaws.com/key
            if self.endpoint_url.startswith("https://s3."):
                base_url = self.endpoint_url.replace("s3.", f"{bucket}.s3.")
                return f"{base_url}/{urllib.parse.quote(key, safe='/')}"
            else:
                # Check if bucket name is already in the endpoint URL
                # (like DigitalOcean Spaces)
                if endpoint_bucket:
                    # Use the bucket from endpoint, ignore the passed bucket parameter
                    quoted_key = urllib.parse.quote(key, safe="/")
                    return f"{self.endpoint_url}/{quoted_key}"
                else:
                    # Path-style URL for custom endpoints
                    quoted_key = urllib.parse.quote(key, safe="/")
                    return f"{self.endpoint_url}/{bucket}/{quoted_key}"
        else:
            # Bucket-only URL
            if self.endpoint_url.startswith("https://s3."):
                return self.endpoint_url.replace("s3.", f"{bucket}.s3.")
            else:
                # Check if bucket name is already in the endpoint URL
                if endpoint_bucket:
                    # Use the bucket from endpoint, ignore the passed bucket parameter
                    return self.endpoint_url
                else:
                    return f"{self.endpoint_url}/{bucket}"

    def _parse_error_response(self, status: int, response_text: str) -> Exception:
        try:
            root = ET.fromstring(response_text)
            error_code = root.find("Code")
            message = root.find("Message")

            error_code_text = error_code.text if error_code is not None else "Unknown"
            message_text = message.text if message is not None else "Unknown error"

        except ET.ParseError:
            error_code_text = "Unknown"
            message_text = response_text or "Unknown error"

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
        await self._ensure_session()

        url = self._build_url(bucket, key)
        request_headers = headers.copy() if headers else {}

        signed_headers = self._auth.sign_request(
            method=method,
            url=url,
            headers=request_headers,
            payload=data or b"",
            query_params=params,
        )

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
        headers = {}

        if content_type:
            headers["Content-Type"] = content_type

        if metadata:
            for key_name, value in metadata.items():
                headers[f"x-amz-meta-{key_name}"] = value

        headers["Content-Length"] = str(len(data))

        response = await self._make_request(
            method="PUT",
            bucket=bucket,
            key=key,
            headers=headers,
            data=data,
        )

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
        response = await self._make_request(
            method="GET",
            bucket=bucket,
            key=key,
        )

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

    async def head_object(
        self,
        bucket: str,
        key: str,
    ) -> dict[str, Any]:
        """Get object metadata without downloading the object."""
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
        response = await self._make_request(
            method="PUT",
            bucket=bucket,
        )

        result = {
            "location": response.headers.get("Location"),
        }

        response.close()
        return result

    async def delete_bucket(
        self,
        bucket: str,
    ) -> dict[str, Any]:
        response = await self._make_request(
            method="DELETE",
            bucket=bucket,
        )

        result = {}

        response.close()
        return result

    async def list_objects(
        self,
        bucket: str,
        prefix: str | None = None,
        max_keys: int = 1000,
        continuation_token: str | None = None,
    ) -> dict[str, Any]:
        params = {
            "list-type": "2",  # Use ListObjectsV2
            "max-keys": str(max_keys),
        }

        if prefix:
            # OVH S3 service requires leading slash in prefix
            # but returns normalized keys
            if "ovh.net" in self.endpoint_url and not prefix.startswith("/"):
                params["prefix"] = "/" + prefix
            else:
                params["prefix"] = prefix

        if continuation_token:
            params["continuation-token"] = continuation_token

        response = await self._make_request(
            method="GET",
            bucket=bucket,
            params=params,
        )

        response_text = await response.text()
        response.close()

        # Handle empty response (some S3 services return empty response
        # for empty buckets)
        if not response_text.strip():
            return {
                "objects": [],
                "is_truncated": False,
                "next_continuation_token": None,
                "prefix": prefix,
                "max_keys": max_keys,
            }

        try:
            root = ET.fromstring(response_text)
        except ET.ParseError as e:
            raise ValueError(
                f"Invalid XML response from S3 service: {e}. "
                f"Response: {response_text[:200]}..."
            )

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

            key_text = key.text if key is not None else ""
            # Normalize key by removing leading slash if present (for OVH compatibility)
            if key_text.startswith("/"):
                key_text = key_text[1:]

            obj = {
                "key": key_text,
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
        url = self._build_url(bucket, key)

        return self._auth.create_presigned_url(
            method=method,
            url=url,
            expires_in=expires_in,
            query_params=params,
        )

    async def upload_file(
        self,
        bucket: str,
        key: str,
        file_source,
        config=None,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
        progress_callback=None,
        **extra_args,
    ) -> dict[str, Any]:
        """Upload a file using automatic single-part or multipart upload.

        Automatically determines whether to use multipart upload based on file size.
        For large files, uses concurrent multipart upload for better performance.
        """
        from .multipart import upload_file

        return await upload_file(
            client=self,
            bucket=bucket,
            key=key,
            file_source=file_source,
            config=config,
            content_type=content_type,
            metadata=metadata,
            progress_callback=progress_callback,
            **extra_args,
        )
