import pytest


@pytest.mark.asyncio
async def test_head_object_basic(mock_client):
    mock_client.add_response(
        "",
        headers={
            "Content-Type": "text/plain",
            "Content-Length": "13",
            "ETag": '"abc123"',
            "Last-Modified": "Wed, 12 Oct 2023 17:50:00 GMT",
        },
    )
    result = await mock_client.head_object(key="test-key")

    assert len(mock_client.requests) == 1
    assert mock_client.requests[0] == {
        "method": "HEAD",
        "key": "test-key",
        "headers": None,
        "params": None,
        "data": None,
    }

    assert result["content_type"] == "text/plain"
    assert result["content_length"] == 13
    assert result["etag"] == "abc123"
    assert result["last_modified"] == "Wed, 12 Oct 2023 17:50:00 GMT"
    assert result["version_id"] is None
    assert result["server_side_encryption"] is None
    assert result["metadata"] == {}
    assert "body" not in result  # HEAD doesn't include body


@pytest.mark.asyncio
async def test_head_object_with_metadata(mock_client):
    mock_client.add_response(
        "m" * 25,
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
    result = await mock_client.head_object("test-key")

    assert result["metadata"]["author"] == "test-user"
    assert result["metadata"]["purpose"] == "testing"
    assert result["version_id"] == "version123"
    assert result["server_side_encryption"] == "AES256"
    assert result["content_type"] == "application/json"
