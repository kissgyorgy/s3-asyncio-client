"""Pytest configuration and fixtures."""

import os

import boto3
import pytest
from moto import mock_aws

from s3_asyncio_client import S3Client


@pytest.fixture
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    return {
        "access_key": "testing",
        "secret_key": "testing",
        "region": "us-east-1",
    }


@pytest.fixture
def s3_client(aws_credentials):
    """Create S3Client for testing."""
    return S3Client(
        access_key=aws_credentials["access_key"],
        secret_key=aws_credentials["secret_key"],
        region=aws_credentials["region"],
        endpoint_url="http://localhost:5000",  # moto endpoint
    )


@pytest.fixture
def mock_s3_setup(aws_credentials):
    """Set up mocked S3 environment."""
    with mock_aws():
        # Set environment variables for moto
        os.environ["AWS_ACCESS_KEY_ID"] = aws_credentials["access_key"]
        os.environ["AWS_SECRET_ACCESS_KEY"] = aws_credentials["secret_key"]
        os.environ["AWS_DEFAULT_REGION"] = aws_credentials["region"]

        # Create boto3 client for setup
        s3 = boto3.client(
            "s3",
            aws_access_key_id=aws_credentials["access_key"],
            aws_secret_access_key=aws_credentials["secret_key"],
            region_name=aws_credentials["region"],
        )

        # Create test bucket
        s3.create_bucket(Bucket="test-bucket")

        yield s3

        # Clean up environment variables
        for key in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION"]:
            os.environ.pop(key, None)
