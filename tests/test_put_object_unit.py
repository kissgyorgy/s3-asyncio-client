import pytest


@pytest.mark.asyncio
async def test_put_object_headers(mock_client):
    mock_client.add_response(
        "",
        headers={
            "ETag": '"abcd1234"',
            "x-amz-version-id": "version123",
        },
    )

    data = b"Hello, World!"
    metadata = {"author": "test", "purpose": "testing"}

    result = await mock_client.put_object(
        key="test-key",
        data=data,
        content_type="text/plain",
        metadata=metadata,
    )

    assert len(mock_client.requests) == 1
    call_args = mock_client.requests[0]

    assert call_args["method"] == "PUT"
    assert call_args["key"] == "test-key"
    assert call_args["data"] == data

    headers = call_args["headers"]
    assert headers["Content-Type"] == "text/plain"
    assert headers["Content-Length"] == str(len(data))
    assert headers["x-amz-meta-author"] == "test"
    assert headers["x-amz-meta-purpose"] == "testing"

    assert result["etag"] == "abcd1234"
    assert result["version_id"] == "version123"


@pytest.mark.asyncio
async def test_put_object_minimal(mock_client):
    mock_client.add_response("", headers={"ETag": '"minimal"'})

    data = b"minimal data"
    result = await mock_client.put_object("key", data)

    assert len(mock_client.requests) == 1
    call_args = mock_client.requests[0]
    headers = call_args["headers"]

    assert "Content-Length" in headers
    assert headers["Content-Length"] == str(len(data))
    assert "Content-Type" not in headers

    assert result["etag"] == "minimal"
    assert result["version_id"] is None
