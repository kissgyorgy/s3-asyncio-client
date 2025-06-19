import configparser
import os
import pathlib
import xml.etree.ElementTree as ET
from typing import Self

import aiohttp
from yarl import URL

from .auth import AWSSignatureV4
from .exceptions import (
    S3AccessDeniedError,
    S3ClientError,
    S3InvalidRequestError,
    S3NotFoundError,
    S3ServerError,
)
from .urlparsing import AddressStyle, get_bucket_url


class _S3ClientBase:
    def __init__(
        self,
        access_key: str,
        secret_key: str,
        region: str,
        endpoint_url: URL | str,
        bucket: str,
        address_style: AddressStyle = AddressStyle.AUTO,
    ):
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.endpoint_url = URL(endpoint_url)
        self.bucket_url = get_bucket_url(self.endpoint_url, bucket, address_style)

        self._auth = AWSSignatureV4(access_key, secret_key, region)
        self._session: aiohttp.ClientSession | None = None

    @classmethod
    def from_aws_config(
        cls,
        bucket: str,
        profile_name: str = "default",
        config_path: str | pathlib.Path | None = None,
        credentials_path: str | pathlib.Path | None = None,
    ) -> Self:
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

        return cls(access_key, secret_key, region, endpoint_url, bucket)

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
        key: str | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        data: bytes | None = None,
    ) -> aiohttp.ClientResponse:
        await self._ensure_session()

        url = self.bucket_url / key if key else self.endpoint_url
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
