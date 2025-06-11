"""Unit tests for put_object method."""

from unittest.mock import AsyncMock, Mock

import pytest

from s3_asyncio_client import S3Client


@pytest.mark.asyncio
async def test_put_object_headers():
    """Test that put_object sets correct headers."""
    client = S3Client("test-key", "test-secret", "us-east-1")

    # Mock the _make_request method
    mock_response = Mock()
    mock_response.headers = {
        "ETag": '"abcd1234"',
        "x-amz-version-id": "version123",
    }

    client._make_request = AsyncMock(return_value=mock_response)

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
    client._make_request.assert_called_once()
    call_args = client._make_request.call_args

    assert call_args[1]["method"] == "PUT"
    assert call_args[1]["bucket"] == "test-bucket"
    assert call_args[1]["key"] == "test-key"
    assert call_args[1]["data"] == data

    headers = call_args[1]["headers"]
    assert headers["Content-Type"] == "text/plain"
    assert headers["Content-Length"] == str(len(data))
    assert headers["x-amz-meta-author"] == "test"
    assert headers["x-amz-meta-purpose"] == "testing"

    # Check result
    assert result["etag"] == "abcd1234"
    assert result["version_id"] == "version123"


@pytest.mark.asyncio
async def test_put_object_minimal():
    """Test put_object with minimal parameters."""
    client = S3Client("test-key", "test-secret", "us-east-1")

    mock_response = Mock()
    mock_response.headers = {"ETag": '"minimal"'}

    client._make_request = AsyncMock(return_value=mock_response)

    data = b"minimal data"
    result = await client.put_object("bucket", "key", data)

    # Check that minimal headers are set
    call_args = client._make_request.call_args
    headers = call_args[1]["headers"]

    assert "Content-Length" in headers
    assert headers["Content-Length"] == str(len(data))
    assert "Content-Type" not in headers  # Should not be set when not provided

    # Check result
    assert result["etag"] == "minimal"
    assert result["version_id"] is None  # Not in response
