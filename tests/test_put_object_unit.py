"""Unit tests for put_object method."""

import pytest

from s3_asyncio_client import S3Client


@pytest.mark.asyncio
async def test_put_object_headers(monkeypatch):
    """Test that put_object sets correct headers."""
    client = S3Client("test-key", "test-secret", "us-east-1")

    # Mock the _make_request method
    class MockResponse:
        headers = {
            "ETag": '"abcd1234"',
            "x-amz-version-id": "version123",
        }

        def close(self):
            pass

    mock_response = MockResponse()

    # Track calls to _make_request
    calls = []

    async def mock_make_request(**kwargs):
        calls.append(kwargs)
        return mock_response

    monkeypatch.setattr(client, "_make_request", mock_make_request)

    data = b"Hello, World!"
    metadata = {"author": "test", "purpose": "testing"}

    result = await client.put_object(
        bucket="test-bucket",
        key="test-key",
        data=data,
        content_type="text/plain",
        metadata=metadata,
    )

    # Check that _make_request was called with correct parameters
    assert len(calls) == 1
    call_args = calls[0]

    assert call_args["method"] == "PUT"
    assert call_args["bucket"] == "test-bucket"
    assert call_args["key"] == "test-key"
    assert call_args["data"] == data

    headers = call_args["headers"]
    assert headers["Content-Type"] == "text/plain"
    assert headers["Content-Length"] == str(len(data))
    assert headers["x-amz-meta-author"] == "test"
    assert headers["x-amz-meta-purpose"] == "testing"

    # Check result
    assert result["etag"] == "abcd1234"
    assert result["version_id"] == "version123"


@pytest.mark.asyncio
async def test_put_object_minimal(monkeypatch):
    """Test put_object with minimal parameters."""
    client = S3Client("test-key", "test-secret", "us-east-1")

    class MockResponse:
        headers = {"ETag": '"minimal"'}

        def close(self):
            pass

    mock_response = MockResponse()

    # Track calls to _make_request
    calls = []

    async def mock_make_request(**kwargs):
        calls.append(kwargs)
        return mock_response

    monkeypatch.setattr(client, "_make_request", mock_make_request)

    data = b"minimal data"
    result = await client.put_object("bucket", "key", data)

    # Check that minimal headers are set
    assert len(calls) == 1
    call_args = calls[0]
    headers = call_args["headers"]

    assert "Content-Length" in headers
    assert headers["Content-Length"] == str(len(data))
    assert "Content-Type" not in headers  # Should not be set when not provided

    # Check result
    assert result["etag"] == "minimal"
    assert result["version_id"] is None  # Not in response
