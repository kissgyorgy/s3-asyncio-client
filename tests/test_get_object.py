from s3_asyncio_client import S3Client


async def test_get_object_basic(monkeypatch):
    client = S3Client("test-key", "test-secret", "us-east-1")

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

    async def mock_make_request(**kwargs):
        calls.append(kwargs)
        return mock_response

    monkeypatch.setattr(client, "_make_request", mock_make_request)

    result = await client.get_object(
        bucket="test-bucket",
        key="test-key",
    )

    assert len(calls) == 1
    assert calls[0] == {
        "method": "GET",
        "bucket": "test-bucket",
        "key": "test-key",
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
    client = S3Client("test-key", "test-secret", "us-east-1")

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

    async def mock_make_request(**kwargs):
        return mock_response

    monkeypatch.setattr(client, "_make_request", mock_make_request)

    result = await client.get_object("test-bucket", "test-key")

    assert result["metadata"]["author"] == "test-user"
    assert result["metadata"]["purpose"] == "testing"
    assert result["version_id"] == "version123"
    assert result["server_side_encryption"] == "AES256"
    assert result["content_type"] == "application/json"


async def test_get_object_empty_content(monkeypatch):
    client = S3Client("test-key", "test-secret", "us-east-1")

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

    async def mock_make_request(**kwargs):
        return mock_response

    monkeypatch.setattr(client, "_make_request", mock_make_request)

    result = await client.get_object("test-bucket", "empty-key")

    assert result["body"] == b""
    assert result["content_length"] == 0
    assert result["etag"] == "empty"


async def test_get_object_binary_data(monkeypatch):
    client = S3Client("test-key", "test-secret", "us-east-1")

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

    async def mock_make_request(**kwargs):
        return mock_response

    monkeypatch.setattr(client, "_make_request", mock_make_request)

    result = await client.get_object("test-bucket", "image.png")

    assert result["body"] == binary_data
    assert result["content_type"] == "image/png"
    assert result["content_length"] == len(binary_data)


async def test_get_object_missing_headers(monkeypatch):
    client = S3Client("test-key", "test-secret", "us-east-1")

    class MockResponse:
        headers = {}

        async def read(self):
            return b"minimal"

        def close(self):
            pass

    mock_response = MockResponse()

    async def mock_make_request(**kwargs):
        return mock_response

    monkeypatch.setattr(client, "_make_request", mock_make_request)

    result = await client.get_object("test-bucket", "minimal-key")

    assert result["body"] == b"minimal"
    assert result["content_type"] is None
    assert result["content_length"] == 0
    assert result["etag"] == ""
    assert result["last_modified"] is None
    assert result["version_id"] is None
    assert result["server_side_encryption"] is None
    assert result["metadata"] == {}
