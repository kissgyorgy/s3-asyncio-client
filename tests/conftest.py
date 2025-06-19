import collections
import configparser
import pathlib
from unittest.mock import AsyncMock, Mock

import pytest

from s3_asyncio_client.client import S3Client


def pytest_addoption(parser):
    parser.addoption(
        "--aws-config",
        action="store",
        default=None,
        help="Path to AWS config file to use for S3Client configuration",
    )


def get_aws_profiles(config_path: str | None) -> list[str]:
    """Parse all profiles from AWS config file. To use in tests for real S3 access."""
    if not config_path:
        config_path = "tmp/ovh_config"

    config_file = pathlib.Path(config_path)
    if not config_file.exists():
        return ["ovh"]

    parser = configparser.ConfigParser()
    parser.read(config_file)

    profiles = []
    for section_name in parser.sections():
        if section_name == "default":
            profiles.append("default")
        elif section_name.startswith("profile "):
            # Config file uses "profile <name>" format
            profile_name = section_name[8:]  # Remove "profile " prefix
            profiles.append(profile_name)
        else:
            # Credentials file uses direct profile names
            profiles.append(section_name)

    return profiles if profiles else ["ovh"]


def pytest_generate_tests(metafunc):
    if "client" not in metafunc.fixturenames:
        return
    aws_config_path = metafunc.config.getoption("--aws-config")
    aws_profiles = get_aws_profiles(aws_config_path)
    metafunc.parametrize("client", aws_profiles, indirect=True)


class MockClient(S3Client):
    def __init__(
        self,
        access_key: str,
        secret_key: str,
        region: str,
        endpoint_url: str,
        bucket: str,
    ):
        super().__init__(
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            endpoint_url=endpoint_url,
            bucket=bucket,
        )
        self._responses = collections.deque()
        self.requests = []

    async def _make_request(
        self,
        method: str,
        key: str | None = None,
        headers: dict | None = None,
        params: dict[str, str] | None = None,
        data: bytes | None = None,
    ):
        self.requests.append(
            {
                "method": method,
                "key": key,
                "headers": headers,
                "params": params,
                "data": data,
            }
        )
        if self._responses:
            return self._responses.popleft()
        raise ValueError("No more responses available in the mock client.")

    def add_response(self, response: str | bytes, headers: dict | None = None):
        amock = AsyncMock()
        amock.text.return_value = response if isinstance(response, str) else None
        amock.read.return_value = (
            response.encode() if isinstance(response, str) else response
        )
        amock.headers = headers or {}
        amock.close = Mock()
        self._responses.append(amock)


@pytest.fixture
def mock_client():
    return MockClient(
        access_key="test-access-key",
        secret_key="test-secret-key",
        region="us-east-1",
        endpoint_url="https://s3.us-east-1.amazonaws.com",
        bucket="test-bucket",
    )
