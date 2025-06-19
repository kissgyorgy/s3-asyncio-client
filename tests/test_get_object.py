import pytest


@pytest.mark.asyncio
async def test_get_object_basic(mock_client):
    mock_client.add_response(
        "Hello, World!",
        {
            "Content-Type": "text/plain",
            "Content-Length": "13",
            "ETag": '"abc123"',
            "Last-Modified": "Wed, 12 Oct 2023 17:50:00 GMT",
        },
    )
    result = await mock_client.get_object(key="test-key")

    assert len(mock_client.requests) == 1
    assert mock_client.requests[0] == {
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


@pytest.mark.asyncio
async def test_get_object_with_metadata(mock_client):
    mock_client.add_response(
        '{"message": "Hello"}',
        headers={
            "Content-Type": "application/json",
            "Content-Length": "25",
            "ETag": '"def456"',
            "x-amz-meta-author": "test-user",
            "x-amz-meta-purpose": "testing",
            "x-amz-version-id": "version123",
            "x-amz-server-side-encryption": "AES256",
        },
    )
    result = await mock_client.get_object("test-key")

    assert result["metadata"]["author"] == "test-user"
    assert result["metadata"]["purpose"] == "testing"
    assert result["version_id"] == "version123"
    assert result["server_side_encryption"] == "AES256"
    assert result["content_type"] == "application/json"


@pytest.mark.asyncio
async def test_get_object_empty_content(mock_client):
    mock_client.add_response("", headers={"Content-Length": "0", "ETag": '"empty"'})
    result = await mock_client.get_object("empty-key")

    assert result["body"] == b""
    assert result["content_length"] == 0
    assert result["etag"] == "empty"


@pytest.mark.asyncio
async def test_get_object_binary_data(mock_client):
    binary_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"  # PNG header
    headers = {
        "Content-Type": "image/png",
        "Content-Length": len(binary_data),
        "ETag": '"binary123"',
    }
    mock_client.add_response(binary_data, headers)

    result = await mock_client.get_object("image.png")

    assert result["body"] == binary_data
    assert result["content_type"] == "image/png"
    assert result["content_length"] == len(binary_data)


@pytest.mark.asyncio
async def test_get_object_missing_headers(mock_client):
    mock_client.add_response("minimal")
    result = await mock_client.get_object("minimal-key")

    assert result["body"] == b"minimal"
    assert result["content_type"] is None
    assert result["content_length"] == 0
    assert result["etag"] == ""
    assert result["last_modified"] is None
    assert result["version_id"] is None
    assert result["server_side_encryption"] is None
    assert result["metadata"] == {}
