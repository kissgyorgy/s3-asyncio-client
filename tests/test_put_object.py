"""Tests for put_object method with moto."""

import os

import boto3
import pytest
from moto import mock_aws

from s3_asyncio_client import S3Client
from s3_asyncio_client.exceptions import S3NotFoundError


@pytest.mark.asyncio
async def test_put_object_basic():
    """Test basic put_object functionality."""
    with mock_aws():
        # Set environment variables for moto
        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        try:
            # Create bucket first with boto3
            s3 = boto3.client("s3", region_name="us-east-1")
            s3.create_bucket(Bucket="test-bucket")

            async with S3Client(
                access_key="testing",
                secret_key="testing",
                region="us-east-1"
            ) as client:
                # Test put_object
                data = b"Hello, World!"
                result = await client.put_object(
                    bucket="test-bucket",
                    key="test-key",
                    data=data,
                )

                assert "etag" in result
                assert result["etag"]
        finally:
            # Clean up environment variables
            env_keys = [
                "AWS_ACCESS_KEY_ID",
                "AWS_SECRET_ACCESS_KEY",
                "AWS_DEFAULT_REGION"
            ]
            for key in env_keys:
                os.environ.pop(key, None)


@pytest.mark.asyncio
async def test_put_object_with_content_type():
    """Test put_object with content type."""
    with mock_aws():
        async with S3Client(
            access_key="testing",
            secret_key="testing",
            region="us-east-1"
        ) as client:
            # Create bucket first
            import boto3
            s3 = boto3.client("s3", region_name="us-east-1")
            s3.create_bucket(Bucket="test-bucket")

            data = b'{"message": "Hello, World!"}'
            result = await client.put_object(
                bucket="test-bucket",
                key="test.json",
                data=data,
                content_type="application/json",
            )

            assert "etag" in result
            assert result["etag"]


@pytest.mark.asyncio
async def test_put_object_with_metadata():
    """Test put_object with custom metadata."""
    with mock_aws():
        async with S3Client(
            access_key="testing",
            secret_key="testing",
            region="us-east-1"
        ) as client:
            # Create bucket first
            import boto3
            s3 = boto3.client("s3", region_name="us-east-1")
            s3.create_bucket(Bucket="test-bucket")

            data = b"Test data with metadata"
            metadata = {
                "author": "test-user",
                "purpose": "testing",
            }

            result = await client.put_object(
                bucket="test-bucket",
                key="test-with-metadata",
                data=data,
                metadata=metadata,
            )

            assert "etag" in result
            assert result["etag"]


@pytest.mark.asyncio
async def test_put_object_nonexistent_bucket():
    """Test put_object with nonexistent bucket raises appropriate error."""
    with mock_aws():
        async with S3Client(
            access_key="testing",
            secret_key="testing",
            region="us-east-1"
        ) as client:
            with pytest.raises(S3NotFoundError):
                await client.put_object(
                    bucket="nonexistent-bucket",
                    key="test-key",
                    data=b"test data",
                )
