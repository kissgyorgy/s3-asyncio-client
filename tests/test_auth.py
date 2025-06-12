"""Tests for AWS Signature Version 4 authentication."""

import hashlib
import urllib.parse
from datetime import datetime
from unittest.mock import patch

import pytest

from s3_asyncio_client.auth import AWSSignatureV4


@pytest.fixture
def auth():
    """Create AWSSignatureV4 instance for testing."""
    return AWSSignatureV4(
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        region="us-east-1",
    )


def test_sha256_hash(auth):
    """Test SHA256 hashing."""
    test_data = b"hello world"
    expected = hashlib.sha256(test_data).hexdigest()
    assert auth._sha256_hash(test_data) == expected


def test_hmac_sha256(auth):
    """Test HMAC-SHA256 signing."""
    key = b"test-key"
    data = "test-data"
    result = auth._hmac_sha256(key, data)
    assert isinstance(result, bytes)
    assert len(result) == 32  # SHA256 produces 32 bytes


def test_get_signature_key(auth):
    """Test signature key derivation."""
    date_stamp = "20230101"
    key = auth._get_signature_key(date_stamp)
    assert isinstance(key, bytes)
    assert len(key) == 32  # SHA256 produces 32 bytes


def test_create_canonical_request(auth):
    """Test canonical request creation."""
    method = "GET"
    uri = "/test-bucket/test-key"
    query_string = "x-amz-algorithm=AWS4-HMAC-SHA256"
    headers = {
        "host": "test-bucket.s3.amazonaws.com",
        "x-amz-date": "20230101T120000Z",
    }
    signed_headers = "host;x-amz-date"
    payload_hash = "UNSIGNED-PAYLOAD"

    canonical_request = auth._create_canonical_request(
        method, uri, query_string, headers, signed_headers, payload_hash
    )

    assert method in canonical_request
    assert uri in canonical_request
    assert query_string in canonical_request
    assert payload_hash in canonical_request
    assert "host:test-bucket.s3.amazonaws.com" in canonical_request


def test_create_string_to_sign(auth):
    """Test string to sign creation."""
    timestamp = "20230101T120000Z"
    date_stamp = "20230101"
    canonical_request = "GET\n/\n\nhost:example.com\n\nhost\nUNSIGNED-PAYLOAD"

    string_to_sign = auth._create_string_to_sign(
        timestamp, date_stamp, canonical_request
    )

    assert "AWS4-HMAC-SHA256" in string_to_sign
    assert timestamp in string_to_sign
    assert "20230101/us-east-1/s3/aws4_request" in string_to_sign


@patch("s3_asyncio_client.auth.datetime")
def test_sign_request(mock_datetime, auth):
    """Test request signing."""
    # Mock datetime
    mock_now = datetime(2023, 1, 1, 12, 0, 0)
    mock_datetime.now.return_value = mock_now

    method = "GET"
    url = "https://test-bucket.s3.amazonaws.com/test-key"
    headers = {"user-agent": "test-client"}

    signed_headers = auth.sign_request(method, url, headers)

    # Check required headers are present
    assert "Authorization" in signed_headers
    assert "x-amz-date" in signed_headers
    assert "host" in signed_headers
    assert "x-amz-content-sha256" in signed_headers

    # Check authorization header format
    auth_header = signed_headers["Authorization"]
    assert auth_header.startswith("AWS4-HMAC-SHA256")
    assert "Credential=" in auth_header
    assert "SignedHeaders=" in auth_header
    assert "Signature=" in auth_header


@patch("s3_asyncio_client.auth.datetime")
def test_sign_request_with_payload(mock_datetime, auth):
    """Test request signing with payload."""
    # Mock datetime
    mock_now = datetime(2023, 1, 1, 12, 0, 0)
    mock_datetime.now.return_value = mock_now

    method = "PUT"
    url = "https://test-bucket.s3.amazonaws.com/test-key"
    payload = b"test content"

    signed_headers = auth.sign_request(method, url, payload=payload)

    # Check payload hash is calculated
    expected_hash = hashlib.sha256(payload).hexdigest()
    assert signed_headers["x-amz-content-sha256"] == expected_hash


@patch("s3_asyncio_client.auth.datetime")
def test_sign_request_with_query_params(mock_datetime, auth):
    """Test request signing with query parameters."""
    # Mock datetime
    mock_now = datetime(2023, 1, 1, 12, 0, 0)
    mock_datetime.now.return_value = mock_now

    method = "GET"
    url = "https://test-bucket.s3.amazonaws.com/test-key"
    query_params = {"prefix": "test", "max-keys": "100"}

    signed_headers = auth.sign_request(method, url, query_params=query_params)

    assert "Authorization" in signed_headers
    # The canonical request should include the query parameters in signing


@patch("s3_asyncio_client.auth.datetime")
def test_create_presigned_url(mock_datetime, auth):
    """Test presigned URL creation."""
    # Mock datetime
    mock_now = datetime(2023, 1, 1, 12, 0, 0)
    mock_datetime.now.return_value = mock_now

    method = "GET"
    url = "https://test-bucket.s3.amazonaws.com/test-key"
    expires_in = 3600

    presigned_url = auth.create_presigned_url(method, url, expires_in)

    # Parse the URL to check query parameters
    parsed = urllib.parse.urlparse(presigned_url)
    query_params = urllib.parse.parse_qs(parsed.query)

    # Check required AWS query parameters
    assert "X-Amz-Algorithm" in query_params
    assert "X-Amz-Credential" in query_params
    assert "X-Amz-Date" in query_params
    assert "X-Amz-Expires" in query_params
    assert "X-Amz-SignedHeaders" in query_params
    assert "X-Amz-Signature" in query_params

    # Check specific values
    assert query_params["X-Amz-Algorithm"][0] == "AWS4-HMAC-SHA256"
    assert query_params["X-Amz-Expires"][0] == str(expires_in)
    assert "AKIAIOSFODNN7EXAMPLE" in query_params["X-Amz-Credential"][0]


@patch("s3_asyncio_client.auth.datetime")
def test_create_presigned_url_with_query_params(mock_datetime, auth):
    """Test presigned URL creation with additional query parameters."""
    # Mock datetime
    mock_now = datetime(2023, 1, 1, 12, 0, 0)
    mock_datetime.now.return_value = mock_now

    method = "GET"
    url = "https://test-bucket.s3.amazonaws.com/test-key"
    query_params = {"response-content-type": "text/plain"}

    presigned_url = auth.create_presigned_url(method, url, query_params=query_params)

    # Check that custom query parameters are included
    parsed = urllib.parse.urlparse(presigned_url)
    query_dict = urllib.parse.parse_qs(parsed.query)
    assert "response-content-type" in query_dict


def test_auth_initialization():
    """Test authentication initialization with different parameters."""
    auth1 = AWSSignatureV4("key", "secret")
    assert auth1.region == "us-east-1"  # default
    assert auth1.service == "s3"  # default

    auth2 = AWSSignatureV4("key", "secret", region="eu-west-1", service="s3")
    assert auth2.region == "eu-west-1"
    assert auth2.service == "s3"


def test_canonical_uri_encoding(auth):
    """Test that URI encoding works correctly in canonical requests."""
    method = "GET"
    uri = "/test bucket/test key with spaces"
    query_string = ""
    headers = {"host": "example.com"}
    signed_headers = "host"
    payload_hash = "UNSIGNED-PAYLOAD"

    canonical_request = auth._create_canonical_request(
        method, uri, query_string, headers, signed_headers, payload_hash
    )

    # Check that the URI is properly encoded
    assert "/test%20bucket/test%20key%20with%20spaces" in canonical_request
