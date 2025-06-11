"""Unit tests for generate_presigned_url method."""

from unittest.mock import Mock

from s3_asyncio_client import S3Client


def test_generate_presigned_url_basic():
    """Test basic presigned URL generation."""
    client = S3Client("test-key", "test-secret", "us-east-1")

    # Mock the auth create_presigned_url method
    client._auth.create_presigned_url = Mock(
        return_value="https://test-bucket.s3.us-east-1.amazonaws.com/test-key?signed-params"
    )

    url = client.generate_presigned_url(
        method="GET",
        bucket="test-bucket",
        key="test-key",
    )

    # Check that auth method was called correctly
    client._auth.create_presigned_url.assert_called_once_with(
        method="GET",
        url="https://test-bucket.s3.us-east-1.amazonaws.com/test-key",
        expires_in=3600,
        query_params=None,
    )

    assert url == "https://test-bucket.s3.us-east-1.amazonaws.com/test-key?signed-params"


def test_generate_presigned_url_with_params():
    """Test presigned URL generation with custom parameters."""
    client = S3Client("test-key", "test-secret", "us-east-1")

    client._auth.create_presigned_url = Mock(
        return_value="https://signed-url-with-params"
    )

    params = {"response-content-type": "text/plain"}
    url = client.generate_presigned_url(
        method="PUT",
        bucket="test-bucket",
        key="upload-key",
        expires_in=1800,
        params=params,
    )

    # Check parameters
    client._auth.create_presigned_url.assert_called_once_with(
        method="PUT",
        url="https://test-bucket.s3.us-east-1.amazonaws.com/upload-key",
        expires_in=1800,
        query_params=params,
    )

    assert url == "https://signed-url-with-params"


def test_generate_presigned_url_custom_endpoint():
    """Test presigned URL generation with custom endpoint."""
    client = S3Client(
        "test-key",
        "test-secret",
        "us-east-1",
        endpoint_url="https://minio.example.com"
    )

    client._auth.create_presigned_url = Mock(
        return_value="https://minio.example.com/bucket/key?signed"
    )

    url = client.generate_presigned_url(
        method="GET",
        bucket="my-bucket",
        key="my-key",
    )

    # Check that custom endpoint URL is used
    client._auth.create_presigned_url.assert_called_once_with(
        method="GET",
        url="https://minio.example.com/my-bucket/my-key",
        expires_in=3600,
        query_params=None,
    )

    assert url == "https://minio.example.com/bucket/key?signed"
