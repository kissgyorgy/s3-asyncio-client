import datetime as dt
import hashlib
import urllib.parse

import pytest

from s3_asyncio_client.auth import AWSSignatureV4


@pytest.fixture
def auth():
    return AWSSignatureV4(
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        region="us-east-1",
    )


@pytest.fixture
def mock_datetime(monkeypatch):
    mock_now = dt.datetime(2023, 1, 1, 12, 0, 0)

    class MockDatetime:
        @staticmethod
        def now(tz=None):
            return mock_now

    class MockDt:
        datetime = MockDatetime
        UTC = dt.UTC

    monkeypatch.setattr("s3_asyncio_client.auth.dt", MockDt)
    return mock_now


def test_sha256_hash(auth):
    test_data = b"hello world"
    expected = hashlib.sha256(test_data).hexdigest()
    assert auth._sha256_hash(test_data) == expected


def test_hmac_sha256(auth):
    key = b"test-key"
    data = "test-data"
    result = auth._hmac_sha256(key, data)
    assert isinstance(result, bytes)
    assert len(result) == 32  # SHA256 produces 32 bytes


def test_get_signature_key(auth):
    date_stamp = "20230101"
    key = auth._get_signature_key(date_stamp)
    assert isinstance(key, bytes)
    assert len(key) == 32  # SHA256 produces 32 bytes


def test_create_canonical_request(auth):
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
    timestamp = "20230101T120000Z"
    date_stamp = "20230101"
    canonical_request = "GET\n/\n\nhost:example.com\n\nhost\nUNSIGNED-PAYLOAD"

    string_to_sign = auth._create_string_to_sign(
        timestamp, date_stamp, canonical_request
    )

    assert "AWS4-HMAC-SHA256" in string_to_sign
    assert timestamp in string_to_sign
    assert "20230101/us-east-1/s3/aws4_request" in string_to_sign


def test_sign_request(auth, mock_datetime):
    method = "GET"
    url = URL("https://test-bucket.s3.amazonaws.com/test-key")
    headers = {"user-agent": "test-client"}

    signed_headers = auth.sign_request(method, url, headers)

    assert "Authorization" in signed_headers
    assert "x-amz-date" in signed_headers
    assert "host" in signed_headers
    assert "x-amz-content-sha256" in signed_headers

    auth_header = signed_headers["Authorization"]
    assert auth_header.startswith("AWS4-HMAC-SHA256")
    assert "Credential=" in auth_header
    assert "SignedHeaders=" in auth_header
    assert "Signature=" in auth_header


def test_sign_request_with_payload(auth, mock_datetime):
    method = "PUT"
    url = URL("https://test-bucket.s3.amazonaws.com/test-key")
    payload = b"test content"

    signed_headers = auth.sign_request(method, url, payload=payload)

    expected_hash = hashlib.sha256(payload).hexdigest()
    assert signed_headers["x-amz-content-sha256"] == expected_hash


def test_sign_request_with_query_params(auth, mock_datetime):
    method = "GET"
    url = URL("https://test-bucket.s3.amazonaws.com/test-key")
    query_params = {"prefix": "test", "max-keys": "100"}

    signed_headers = auth.sign_request(method, url, query_params=query_params)

    assert "Authorization" in signed_headers
    # The canonical request should include the query parameters in signing


def test_create_presigned_url(auth, mock_datetime):
    method = "GET"
    url = URL("https://test-bucket.s3.amazonaws.com/test-key")
    expires_in = 3600

    presigned_url = auth.create_presigned_url(method, url, expires_in)

    parsed = urllib.parse.urlparse(presigned_url)
    query_params = urllib.parse.parse_qs(parsed.query)

    assert "X-Amz-Algorithm" in query_params
    assert "X-Amz-Credential" in query_params
    assert "X-Amz-Date" in query_params
    assert "X-Amz-Expires" in query_params
    assert "X-Amz-SignedHeaders" in query_params
    assert "X-Amz-Signature" in query_params

    assert query_params["X-Amz-Algorithm"][0] == "AWS4-HMAC-SHA256"
    assert query_params["X-Amz-Expires"][0] == str(expires_in)
    assert "AKIAIOSFODNN7EXAMPLE" in query_params["X-Amz-Credential"][0]


def test_create_presigned_url_with_query_params(auth, mock_datetime):
    method = "GET"
    url = URL("https://test-bucket.s3.amazonaws.com/test-key")
    query_params = {"response-content-type": "text/plain"}

    presigned_url = auth.create_presigned_url(method, url, query_params=query_params)

    parsed = urllib.parse.urlparse(presigned_url)
    query_dict = urllib.parse.parse_qs(parsed.query)
    assert "response-content-type" in query_dict


def test_auth_initialization():
    auth1 = AWSSignatureV4("key", "secret")
    assert auth1.region == "us-east-1"  # default

    auth2 = AWSSignatureV4("key", "secret", region="eu-west-1")
    assert auth2.region == "eu-west-1"


def test_canonical_uri_encoding(auth):
    method = "GET"
    uri = "/test bucket/test key with spaces"
    query_string = ""
    headers = {"host": "example.com"}
    signed_headers = "host"
    payload_hash = "UNSIGNED-PAYLOAD"

    canonical_request = auth._create_canonical_request(
        method, uri, query_string, headers, signed_headers, payload_hash
    )

    assert "/test%20bucket/test%20key%20with%20spaces" in canonical_request
