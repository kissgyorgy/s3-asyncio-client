from s3_asyncio_client import S3Client


def test_generate_presigned_url_basic(monkeypatch):
    client = S3Client("test-key", "test-secret", "us-east-1")

    calls = []

    def mock_create_presigned_url(**kwargs):
        calls.append(kwargs)
        return "https://test-bucket.s3.us-east-1.amazonaws.com/test-key?signed-params"

    monkeypatch.setattr(client._auth, "create_presigned_url", mock_create_presigned_url)

    url = client.generate_presigned_url(
        method="GET",
        bucket="test-bucket",
        key="test-key",
    )

    assert len(calls) == 1
    assert calls[0] == {
        "method": "GET",
        "url": "https://test-bucket.s3.us-east-1.amazonaws.com/test-key",
        "expires_in": 3600,
        "query_params": None,
    }

    assert (
        url == "https://test-bucket.s3.us-east-1.amazonaws.com/test-key?signed-params"
    )


def test_generate_presigned_url_with_params(monkeypatch):
    client = S3Client("test-key", "test-secret", "us-east-1")

    calls = []

    def mock_create_presigned_url(**kwargs):
        calls.append(kwargs)
        return "https://signed-url-with-params"

    monkeypatch.setattr(client._auth, "create_presigned_url", mock_create_presigned_url)

    params = {"response-content-type": "text/plain"}
    url = client.generate_presigned_url(
        method="PUT",
        bucket="test-bucket",
        key="upload-key",
        expires_in=1800,
        params=params,
    )

    assert len(calls) == 1
    assert calls[0] == {
        "method": "PUT",
        "url": "https://test-bucket.s3.us-east-1.amazonaws.com/upload-key",
        "expires_in": 1800,
        "query_params": params,
    }

    assert url == "https://signed-url-with-params"


def test_generate_presigned_url_custom_endpoint(monkeypatch):
    client = S3Client(
        "test-key", "test-secret", "us-east-1", endpoint_url="https://minio.example.com"
    )

    calls = []

    def mock_create_presigned_url(**kwargs):
        calls.append(kwargs)
        return "https://minio.example.com/bucket/key?signed"

    monkeypatch.setattr(client._auth, "create_presigned_url", mock_create_presigned_url)

    url = client.generate_presigned_url(
        method="GET",
        bucket="my-bucket",
        key="my-key",
    )

    assert len(calls) == 1
    assert calls[0] == {
        "method": "GET",
        "url": "https://minio.example.com/my-bucket/my-key",
        "expires_in": 3600,
        "query_params": None,
    }

    assert url == "https://minio.example.com/bucket/key?signed"
