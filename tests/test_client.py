"""Tests for S3Client."""

import pytest

from s3_asyncio_client.client import S3Client
from s3_asyncio_client.exceptions import (
    S3AccessDeniedError,
    S3ClientError,
    S3InvalidRequestError,
    S3NotFoundError,
    S3ServerError,
)


@pytest.fixture
def client():
    """Create S3Client instance for testing."""
    return S3Client(
        access_key="test-access-key",
        secret_key="test-secret-key",
        region="us-east-1",
    )


@pytest.fixture
def client_custom_endpoint():
    """Create S3Client with custom endpoint for testing."""
    return S3Client(
        access_key="test-access-key",
        secret_key="test-secret-key",
        region="us-east-1",
        endpoint_url="https://minio.example.com",
    )


def test_client_initialization(client):
    """Test client initialization."""
    assert client.access_key == "test-access-key"
    assert client.secret_key == "test-secret-key"
    assert client.region == "us-east-1"
    assert client.endpoint_url == "https://s3.us-east-1.amazonaws.com"
    assert client._session is None


def test_client_initialization_custom_endpoint(client_custom_endpoint):
    """Test client initialization with custom endpoint."""
    assert client_custom_endpoint.endpoint_url == "https://minio.example.com"


def test_build_url_virtual_hosted_style(client):
    """Test URL building with virtual hosted-style."""
    # Bucket only
    url = client._build_url("test-bucket")
    assert url == "https://test-bucket.s3.us-east-1.amazonaws.com"

    # Bucket and key
    url = client._build_url("test-bucket", "path/to/file.txt")
    assert url == "https://test-bucket.s3.us-east-1.amazonaws.com/path/to/file.txt"

    # Key with special characters
    url = client._build_url("test-bucket", "path with spaces/file.txt")
    assert (
        url
        == "https://test-bucket.s3.us-east-1.amazonaws.com/path%20with%20spaces/file.txt"
    )


def test_build_url_path_style(client_custom_endpoint):
    """Test URL building with path-style for custom endpoints."""
    # Bucket only
    url = client_custom_endpoint._build_url("test-bucket")
    assert url == "https://minio.example.com/test-bucket"

    # Bucket and key
    url = client_custom_endpoint._build_url("test-bucket", "path/to/file.txt")
    assert url == "https://minio.example.com/test-bucket/path/to/file.txt"


def test_parse_error_response_xml(client):
    """Test parsing of XML error responses."""
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <Error>
        <Code>NoSuchKey</Code>
        <Message>The specified key does not exist.</Message>
        <Key>nonexistent-key</Key>
        <BucketName>test-bucket</BucketName>
    </Error>"""

    exception = client._parse_error_response(404, xml_response)
    assert isinstance(exception, S3NotFoundError)
    assert "specified key does not exist" in str(exception)


def test_parse_error_response_access_denied(client):
    """Test parsing of access denied error."""
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <Error>
        <Code>AccessDenied</Code>
        <Message>Access Denied</Message>
    </Error>"""

    exception = client._parse_error_response(403, xml_response)
    assert isinstance(exception, S3AccessDeniedError)


def test_parse_error_response_invalid_request(client):
    """Test parsing of invalid request error."""
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <Error>
        <Code>InvalidRequest</Code>
        <Message>Invalid request</Message>
    </Error>"""

    exception = client._parse_error_response(400, xml_response)
    assert isinstance(exception, S3InvalidRequestError)


def test_parse_error_response_client_error(client):
    """Test parsing of generic client error."""
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <Error>
        <Code>SomeClientError</Code>
        <Message>Some client error</Message>
    </Error>"""

    exception = client._parse_error_response(400, xml_response)
    assert isinstance(exception, S3ClientError)
    assert exception.status_code == 400
    assert exception.error_code == "SomeClientError"


def test_parse_error_response_server_error(client):
    """Test parsing of server error."""
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <Error>
        <Code>InternalError</Code>
        <Message>We encountered an internal error</Message>
    </Error>"""

    exception = client._parse_error_response(500, xml_response)
    assert isinstance(exception, S3ServerError)
    assert exception.status_code == 500


def test_parse_error_response_malformed_xml(client):
    """Test parsing of malformed XML response."""
    malformed_xml = "<Error><Code>Test</Error>"  # Missing closing tag

    exception = client._parse_error_response(500, malformed_xml)
    assert isinstance(exception, S3ServerError)
    assert malformed_xml in str(exception)


def test_parse_error_response_no_xml(client):
    """Test parsing of non-XML error response."""
    plain_text = "Internal Server Error"

    exception = client._parse_error_response(500, plain_text)
    assert isinstance(exception, S3ServerError)
    assert "Internal Server Error" in str(exception)


def test_parse_error_response_status_code_precedence(client):
    """Test that status code takes precedence over error code for specific errors."""
    # 404 status should create S3NotFoundError regardless of error code
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <Error>
        <Code>SomeOtherError</Code>
        <Message>Not found</Message>
    </Error>"""

    exception = client._parse_error_response(404, xml_response)
    assert isinstance(exception, S3NotFoundError)


async def test_context_manager():
    """Test async context manager functionality."""
    async with S3Client("key", "secret") as client:
        assert client._session is not None
    # Session should be closed after exiting context


@pytest.mark.asyncio
async def test_methods_are_implemented(client):
    """Test that methods are implemented and don't raise NotImplementedError."""
    # Mock the _make_request method to avoid actual network calls
    from unittest.mock import AsyncMock, Mock
    
    mock_response = Mock()
    mock_response.headers = {"ETag": '"test"'}
    mock_response.read = AsyncMock(return_value=b"test")
    mock_response.text = AsyncMock(return_value="<xml>test</xml>")
    
    client._make_request = AsyncMock(return_value=mock_response)
    client._auth.create_presigned_url = Mock(return_value="https://example.com")
    
    # These should not raise NotImplementedError anymore
    await client.put_object("bucket", "key", b"data")
    await client.get_object("bucket", "key")
    await client.head_object("bucket", "key")
    await client.list_objects("bucket")
    client.generate_presigned_url("GET", "bucket", "key")


@pytest.mark.asyncio
async def test_ensure_session(client):
    """Test session creation."""
    assert client._session is None
    await client._ensure_session()
    assert client._session is not None
    await client.close()


@pytest.mark.asyncio
async def test_close_session(client):
    """Test session cleanup."""
    await client._ensure_session()
    assert client._session is not None
    await client.close()
    assert client._session is None


