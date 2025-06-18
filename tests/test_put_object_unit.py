from s3_asyncio_client import S3Client


async def test_put_object_headers(monkeypatch):
    client = S3Client(
        access_key="test-key",
        secret_key="test-secret",
        region="us-east-1",
        endpoint_url="https://s3.us-east-1.amazonaws.com",
        bucket="test-bucket",
    )

    class MockResponse:
        headers = {
            "ETag": '"abcd1234"',
            "x-amz-version-id": "version123",
        }

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

    data = b"Hello, World!"
    metadata = {"author": "test", "purpose": "testing"}

    result = await client.put_object(
        key="test-key",
        data=data,
        content_type="text/plain",
        metadata=metadata,
    )

    assert len(calls) == 1
    call_args = calls[0]

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


async def test_put_object_minimal(monkeypatch):
    client = S3Client(
        access_key="test-key",
        secret_key="test-secret",
        region="us-east-1",
        endpoint_url="https://s3.us-east-1.amazonaws.com",
        bucket="test-bucket",
    )

    class MockResponse:
        headers = {"ETag": '"minimal"'}

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

    data = b"minimal data"
    result = await client.put_object("key", data)

    assert len(calls) == 1
    call_args = calls[0]
    headers = call_args["headers"]

    assert "Content-Length" in headers
    assert headers["Content-Length"] == str(len(data))
    assert "Content-Type" not in headers

    assert result["etag"] == "minimal"
    assert result["version_id"] is None
