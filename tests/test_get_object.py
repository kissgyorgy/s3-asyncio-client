from s3_asyncio_client import S3Client


async def test_get_object_basic(monkeypatch):
    client = S3Client(
        access_key="test-key",
        secret_key="test-secret",
        region="us-east-1",
        endpoint_url="https://s3.us-east-1.amazonaws.com",
        bucket="test-bucket",
    )

    class MockResponse:
        headers = {
            "Content-Type": "text/plain",
            "Content-Length": "13",
            "ETag": '"abc123"',
            "Last-Modified": "Wed, 12 Oct 2023 17:50:00 GMT",
        }

        async def read(self):
            return b"Hello, World!"

        def close(self):
            pass

    mock_response = MockResponse()

    calls = []

    async def mock_make_request(method, key=None, headers=None, params=None, data=None):
        calls.append(
            {
                "method": method,
                "key": key,
                "headers": headers,
                "params": params,
                "data": data,
            }
        )
        return mock_response

    monkeypatch.setattr(client, "_make_request", mock_make_request)

    result = await client.get_object(
        key="test-key",
    )

    assert len(calls) == 1
    assert calls[0] == {
        "method": "GET",
        "key": "test-key",
        "headers": None,
        "params": None,
        "data": None,
    }

    assert result["body"] == b"Hello, World!"
    assert result["content_type"] == "text/plain"
    assert result["content_length"] == 13
    assert result["etag"] == "abc123"
    assert result["last_modified"] == "Wed, 12 Oct 2023 17:50:00 GMT"
    assert result["version_id"] is None
    assert result["server_side_encryption"] is None
    assert result["metadata"] == {}


async def test_get_object_with_metadata(monkeypatch):
    client = S3Client(
        access_key="test-key",
        secret_key="test-secret",
        region="us-east-1",
        endpoint_url="https://s3.us-east-1.amazonaws.com",
        bucket="test-bucket",
    )

    class MockResponse:
        headers = {
            "Content-Type": "application/json",
            "Content-Length": "25",
            "ETag": '"def456"',
            "x-amz-meta-author": "test-user",
            "x-amz-meta-purpose": "testing",
            "x-amz-version-id": "version123",
            "x-amz-server-side-encryption": "AES256",
        }

        async def read(self):
            return b'{"message": "Hello"}'

        def close(self):
            pass

    mock_response = MockResponse()

    async def mock_make_request(method, key=None, headers=None, params=None, data=None):
        return mock_response

    monkeypatch.setattr(client, "_make_request", mock_make_request)

    result = await client.get_object("test-key")

    assert result["metadata"]["author"] == "test-user"
    assert result["metadata"]["purpose"] == "testing"
    assert result["version_id"] == "version123"
    assert result["server_side_encryption"] == "AES256"
    assert result["content_type"] == "application/json"


async def test_get_object_empty_content(monkeypatch):
    client = S3Client(
        access_key="test-key",
        secret_key="test-secret",
        region="us-east-1",
        endpoint_url="https://s3.us-east-1.amazonaws.com",
        bucket="test-bucket",
    )

    class MockResponse:
        headers = {
            "Content-Length": "0",
            "ETag": '"empty"',
        }

        async def read(self):
            return b""

        def close(self):
            pass

    mock_response = MockResponse()

    async def mock_make_request(method, key=None, headers=None, params=None, data=None):
        return mock_response

    monkeypatch.setattr(client, "_make_request", mock_make_request)

    result = await client.get_object("empty-key")

    assert result["body"] == b""
    assert result["content_length"] == 0
    assert result["etag"] == "empty"


async def test_get_object_binary_data(monkeypatch):
    client = S3Client(
        access_key="test-key",
        secret_key="test-secret",
        region="us-east-1",
        endpoint_url="https://s3.us-east-1.amazonaws.com",
        bucket="test-bucket",
    )

    binary_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"  # PNG header

    class MockResponse:
        headers = {
            "Content-Type": "image/png",
            "Content-Length": str(len(binary_data)),
            "ETag": '"binary123"',
        }

        async def read(self):
            return binary_data

        def close(self):
            pass

    mock_response = MockResponse()

    async def mock_make_request(method, key=None, headers=None, params=None, data=None):
        return mock_response

    monkeypatch.setattr(client, "_make_request", mock_make_request)

    result = await client.get_object("image.png")

    assert result["body"] == binary_data
    assert result["content_type"] == "image/png"
    assert result["content_length"] == len(binary_data)


async def test_get_object_missing_headers(monkeypatch):
    client = S3Client(
        access_key="test-key",
        secret_key="test-secret",
        region="us-east-1",
        endpoint_url="https://s3.us-east-1.amazonaws.com",
        bucket="test-bucket",
    )

    class MockResponse:
        headers = {}

        async def read(self):
            return b"minimal"

        def close(self):
            pass

    mock_response = MockResponse()

    async def mock_make_request(method, key=None, headers=None, params=None, data=None):
        return mock_response

    monkeypatch.setattr(client, "_make_request", mock_make_request)

    result = await client.get_object("minimal-key")

    assert result["body"] == b"minimal"
    assert result["content_type"] is None
    assert result["content_length"] == 0
    assert result["etag"] == ""
    assert result["last_modified"] is None
    assert result["version_id"] is None
    assert result["server_side_encryption"] is None
    assert result["metadata"] == {}
