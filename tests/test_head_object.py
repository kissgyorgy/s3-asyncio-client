from s3_asyncio_client import S3Client


async def test_head_object_basic(monkeypatch):
    client = S3Client("test-key", "test-secret", "us-east-1")

    class MockResponse:
        headers = {
            "Content-Type": "text/plain",
            "Content-Length": "13",
            "ETag": '"abc123"',
            "Last-Modified": "Wed, 12 Oct 2023 17:50:00 GMT",
        }

        def close(self):
            pass

    mock_response = MockResponse()

    calls = []

    async def mock_make_request(**kwargs):
        calls.append(kwargs)
        return mock_response

    monkeypatch.setattr(client, "_make_request", mock_make_request)

    result = await client.head_object(
        bucket="test-bucket",
        key="test-key",
    )

    assert len(calls) == 1
    assert calls[0] == {
        "method": "HEAD",
        "bucket": "test-bucket",
        "key": "test-key",
    }

    assert result["content_type"] == "text/plain"
    assert result["content_length"] == 13
    assert result["etag"] == "abc123"
    assert result["last_modified"] == "Wed, 12 Oct 2023 17:50:00 GMT"
    assert result["version_id"] is None
    assert result["server_side_encryption"] is None
    assert result["metadata"] == {}
    assert "body" not in result  # HEAD doesn't include body


async def test_head_object_with_metadata(monkeypatch):
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

        def close(self):
            pass

    mock_response = MockResponse()

    async def mock_make_request(**kwargs):
        return mock_response

    monkeypatch.setattr(client, "_make_request", mock_make_request)

    result = await client.head_object("test-bucket", "test-key")

    assert result["metadata"]["author"] == "test-user"
    assert result["metadata"]["purpose"] == "testing"
    assert result["version_id"] == "version123"
    assert result["server_side_encryption"] == "AES256"
    assert result["content_type"] == "application/json"
