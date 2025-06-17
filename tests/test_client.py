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
    return S3Client(
        access_key="test-access-key",
        secret_key="test-secret-key",
        region="us-east-1",
    )


@pytest.fixture
def client_custom_endpoint():
    return S3Client(
        access_key="test-access-key",
        secret_key="test-secret-key",
        region="us-east-1",
        endpoint_url="https://minio.example.com",
    )


def test_client_initialization(client):
    assert client.access_key == "test-access-key"
    assert client.secret_key == "test-secret-key"
    assert client.region == "us-east-1"
    assert client.endpoint_url == "https://s3.us-east-1.amazonaws.com"
    assert client._session is None


def test_client_initialization_custom_endpoint(client_custom_endpoint):
    assert client_custom_endpoint.endpoint_url == "https://minio.example.com"


def test_build_url_virtual_hosted_style(client):
    url = client._build_url("test-bucket")
    assert url == "https://test-bucket.s3.us-east-1.amazonaws.com"

    url = client._build_url("test-bucket", "path/to/file.txt")
    assert url == "https://test-bucket.s3.us-east-1.amazonaws.com/path/to/file.txt"

    url = client._build_url("test-bucket", "path with spaces/file.txt")
    assert (
        url
        == "https://test-bucket.s3.us-east-1.amazonaws.com/path%20with%20spaces/file.txt"
    )


def test_build_url_path_style(client_custom_endpoint):
    url = client_custom_endpoint._build_url("test-bucket")
    assert url == "https://minio.example.com/test-bucket"

    url = client_custom_endpoint._build_url("test-bucket", "path/to/file.txt")
    assert url == "https://minio.example.com/test-bucket/path/to/file.txt"


def test_parse_error_response_xml(client):
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
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <Error>
        <Code>AccessDenied</Code>
        <Message>Access Denied</Message>
    </Error>"""

    exception = client._parse_error_response(403, xml_response)
    assert isinstance(exception, S3AccessDeniedError)


def test_parse_error_response_invalid_request(client):
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <Error>
        <Code>InvalidRequest</Code>
        <Message>Invalid request</Message>
    </Error>"""

    exception = client._parse_error_response(400, xml_response)
    assert isinstance(exception, S3InvalidRequestError)


def test_parse_error_response_client_error(client):
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
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <Error>
        <Code>InternalError</Code>
        <Message>We encountered an internal error</Message>
    </Error>"""

    exception = client._parse_error_response(500, xml_response)
    assert isinstance(exception, S3ServerError)
    assert exception.status_code == 500


def test_parse_error_response_malformed_xml(client):
    malformed_xml = "<Error><Code>Test</Error>"  # Missing closing tag

    exception = client._parse_error_response(500, malformed_xml)
    assert isinstance(exception, S3ServerError)
    assert malformed_xml in str(exception)


def test_parse_error_response_no_xml(client):
    plain_text = "Internal Server Error"

    exception = client._parse_error_response(500, plain_text)
    assert isinstance(exception, S3ServerError)
    assert "Internal Server Error" in str(exception)


def test_parse_error_response_status_code_precedence(client):
    # 404 status should create S3NotFoundError regardless of error code
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <Error>
        <Code>SomeOtherError</Code>
        <Message>Not found</Message>
    </Error>"""

    exception = client._parse_error_response(404, xml_response)
    assert isinstance(exception, S3NotFoundError)


async def test_context_manager():
    async with S3Client("key", "secret") as client:
        assert client._session is not None
    # Session should be closed after exiting context


async def test_methods_are_implemented(client, monkeypatch):
    class MockResponse:
        headers = {"ETag": '"test"'}

        async def read(self):
            return b"test"

        async def text(self):
            return "<xml>test</xml>"

        def close(self):
            pass

    mock_response = MockResponse()

    async def mock_make_request(**kwargs):
        return mock_response

    def mock_create_presigned_url(**kwargs):
        return "https://example.com"

    monkeypatch.setattr(client, "_make_request", mock_make_request)
    monkeypatch.setattr(client._auth, "create_presigned_url", mock_create_presigned_url)

    await client.put_object("bucket", "key", b"data")
    await client.get_object("bucket", "key")
    await client.head_object("bucket", "key")
    await client.list_objects("bucket")
    client.generate_presigned_url("GET", "bucket", "key")


async def test_ensure_session(client):
    assert client._session is None
    await client._ensure_session()
    assert client._session is not None
    await client.close()


async def test_close_session(client):
    await client._ensure_session()
    assert client._session is not None
    await client.close()
    assert client._session is None


async def test_create_bucket(client, monkeypatch):
    class MockResponse:
        headers = {"Location": "https://test-bucket.s3.amazonaws.com/"}

        def close(self):
            pass

    mock_response = MockResponse()

    calls = []

    async def mock_make_request(**kwargs):
        calls.append(kwargs)
        return mock_response

    monkeypatch.setattr(client, "_make_request", mock_make_request)

    result = await client.create_bucket("test-bucket")

    assert len(calls) == 1
    call_args = calls[0]

    assert call_args["method"] == "PUT"
    assert call_args["bucket"] == "test-bucket"
    assert call_args.get("key") is None
    assert call_args.get("headers") is None
    assert call_args.get("params") is None
    assert call_args.get("data") is None

    assert result["location"] == "https://test-bucket.s3.amazonaws.com/"
