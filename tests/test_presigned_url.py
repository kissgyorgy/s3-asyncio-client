from s3_asyncio_client import S3Client


def test_generate_presigned_url_basic(monkeypatch):
    client = S3Client(
        access_key="test-key",
        secret_key="test-secret",
        region="us-east-1",
        endpoint_url="https://s3.us-east-1.amazonaws.com",
        bucket="test-bucket",
    )

    calls = []

    def mock_create_presigned_url(method, url, expires_in=3600, query_params=None):
        calls.append(
            {
                "method": method,
                "url": str(url),
                "expires_in": expires_in,
                "query_params": query_params,
            }
        )
        return "https://test-bucket.s3.us-east-1.amazonaws.com/test-key?signed-params"

    monkeypatch.setattr(client._auth, "create_presigned_url", mock_create_presigned_url)

    url = client.generate_presigned_url(
        method="GET",
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
    client = S3Client(
        access_key="test-key",
        secret_key="test-secret",
        region="us-east-1",
        endpoint_url="https://s3.us-east-1.amazonaws.com",
        bucket="test-bucket",
    )

    calls = []

    def mock_create_presigned_url(method, url, expires_in=3600, query_params=None):
        calls.append(
            {
                "method": method,
                "url": str(url),
                "expires_in": expires_in,
                "query_params": query_params,
            }
        )
        return "https://signed-url-with-params"

    monkeypatch.setattr(client._auth, "create_presigned_url", mock_create_presigned_url)

    params = {"response-content-type": "text/plain"}
    url = client.generate_presigned_url(
        method="PUT",
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
        access_key="test-key",
        secret_key="test-secret",
        region="us-east-1",
        endpoint_url="https://minio.example.com",
        bucket="my-bucket",
    )

    calls = []

    def mock_create_presigned_url(method, url, expires_in=3600, query_params=None):
        calls.append(
            {
                "method": method,
                "url": str(url),
                "expires_in": expires_in,
                "query_params": query_params,
            }
        )
        return "https://minio.example.com/bucket/key?signed"

    monkeypatch.setattr(client._auth, "create_presigned_url", mock_create_presigned_url)

    url = client.generate_presigned_url(
        method="GET",
        key="my-key",
    )

    assert len(calls) == 1
    assert calls[0] == {
        "method": "GET",
        "url": "https://my-bucket.minio.example.com/my-key",
        "expires_in": 3600,
        "query_params": None,
    }

    assert url == "https://minio.example.com/bucket/key?signed"
