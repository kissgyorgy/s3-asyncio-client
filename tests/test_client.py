import pytest

from s3_asyncio_client.client import S3Client
from s3_asyncio_client.exceptions import (
    S3AccessDeniedError,
    S3ClientError,
    S3InvalidRequestError,
    S3NotFoundError,
    S3ServerError,
)


@pytest.fixture
def client_custom_endpoint():
    return S3Client(
        access_key="test-access-key",
        secret_key="test-secret-key",
        region="us-east-1",
        endpoint_url="https://minio.example.com",
        bucket="test-bucket",
    )


def test_client_initialization(mock_client):
    assert mock_client.access_key == "test-access-key"
    assert mock_client.secret_key == "test-secret-key"
    assert mock_client.region == "us-east-1"
    assert (
        str(mock_client.bucket_url) == "https://test-bucket.s3.us-east-1.amazonaws.com"
    )
    assert mock_client._session is None


def test_client_initialization_custom_endpoint(client_custom_endpoint):
    assert (
        str(client_custom_endpoint.bucket_url)
        == "https://test-bucket.minio.example.com"
    )


def test_parse_error_response_xml(mock_client):
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <Error>
        <Code>NoSuchKey</Code>
        <Message>The specified key does not exist.</Message>
        <Key>nonexistent-key</Key>
        <BucketName>test-bucket</BucketName>
    </Error>"""

    exception = mock_client._parse_error_response(404, xml_response)
    assert isinstance(exception, S3NotFoundError)
    assert "specified key does not exist" in str(exception)


def test_parse_error_response_access_denied(mock_client):
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <Error>
        <Code>AccessDenied</Code>
        <Message>Access Denied</Message>
    </Error>"""

    exception = mock_client._parse_error_response(403, xml_response)
    assert isinstance(exception, S3AccessDeniedError)


def test_parse_error_response_invalid_request(mock_client):
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <Error>
        <Code>InvalidRequest</Code>
        <Message>Invalid request</Message>
    </Error>"""

    exception = mock_client._parse_error_response(400, xml_response)
    assert isinstance(exception, S3InvalidRequestError)


def test_parse_error_response_client_error(mock_client):
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <Error>
        <Code>SomeClientError</Code>
        <Message>Some client error</Message>
    </Error>"""

    exception = mock_client._parse_error_response(400, xml_response)
    assert isinstance(exception, S3ClientError)
    assert exception.status_code == 400
    assert exception.error_code == "SomeClientError"


def test_parse_error_response_server_error(mock_client):
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <Error>
        <Code>InternalError</Code>
        <Message>We encountered an internal error</Message>
    </Error>"""

    exception = mock_client._parse_error_response(500, xml_response)
    assert isinstance(exception, S3ServerError)
    assert exception.status_code == 500


def test_parse_error_response_malformed_xml(mock_client):
    malformed_xml = "<Error><Code>Test</Error>"  # Missing closing tag

    exception = mock_client._parse_error_response(500, malformed_xml)
    assert isinstance(exception, S3ServerError)
    assert malformed_xml in str(exception)


def test_parse_error_response_no_xml(mock_client):
    plain_text = "Internal Server Error"

    exception = mock_client._parse_error_response(500, plain_text)
    assert isinstance(exception, S3ServerError)
    assert "Internal Server Error" in str(exception)


def test_parse_error_response_status_code_precedence(mock_client):
    # 404 status should create S3NotFoundError regardless of error code
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <Error>
        <Code>SomeOtherError</Code>
        <Message>Not found</Message>
    </Error>"""

    exception = mock_client._parse_error_response(404, xml_response)
    assert isinstance(exception, S3NotFoundError)


async def test_context_manager():
    async with S3Client(
        "key", "secret", "us-east-1", "https://s3.amazonaws.com", "test-bucket"
    ) as client:
        assert client._session is not None
    assert client._session is None


@pytest.mark.asyncio
async def test_ensure_session(mock_client):
    assert mock_client._session is None
    await mock_client._ensure_session()
    assert mock_client._session is not None
    await mock_client.close()


@pytest.mark.asyncio
async def test_close_session(mock_client):
    await mock_client._ensure_session()
    assert mock_client._session is not None
    await mock_client.close()
    assert mock_client._session is None


@pytest.mark.asyncio
async def test_create_bucket(mock_client):
    mock_client.add_response(
        "", headers={"Location": "https://test-bucket.s3.amazonaws.com/"}
    )

    result = await mock_client.create_bucket()

    assert len(mock_client.requests) == 1
    call_args = mock_client.requests[0]

    assert call_args["method"] == "PUT"
    assert call_args.get("key") is None
    assert call_args.get("headers") is None
    assert call_args.get("params") is None
    assert call_args.get("data") is None

    assert result["location"] == "https://test-bucket.s3.amazonaws.com/"


@pytest.mark.asyncio
async def test_create_bucket_with_region(mock_client):
    mock_client.add_response(
        "", headers={"Location": "https://test-bucket.s3.eu-west-1.amazonaws.com/"}
    )
    result = await mock_client.create_bucket(region="eu-west-1")

    assert len(mock_client.requests) == 1
    call_args = mock_client.requests[0]

    assert call_args["method"] == "PUT"
    assert call_args.get("key") is None
    assert call_args["headers"]["Content-Type"] == "application/xml"
    assert call_args.get("params") is None

    # Check that the XML body contains the LocationConstraint
    data = call_args["data"].decode("utf-8")
    assert "<LocationConstraint>eu-west-1</LocationConstraint>" in data
    assert "CreateBucketConfiguration" in data

    assert result["location"] == "https://test-bucket.s3.eu-west-1.amazonaws.com/"


@pytest.mark.asyncio
async def test_create_bucket_us_east_1_no_location_constraint(mock_client):
    mock_client.add_response(
        "", headers={"Location": "https://test-bucket.s3.amazonaws.com/"}
    )
    result = await mock_client.create_bucket(region="us-east-1")

    assert len(mock_client.requests) == 1
    call_args = mock_client.requests[0]

    assert call_args["method"] == "PUT"
    assert call_args.get("key") is None
    assert call_args.get("headers") is None  # No headers for us-east-1
    assert call_args.get("params") is None
    assert call_args.get("data") is None  # No data for us-east-1

    assert result["location"] == "https://test-bucket.s3.amazonaws.com/"


@pytest.mark.asyncio
async def test_create_bucket_with_acl_and_object_lock(mock_client):
    mock_client.add_response(
        "", headers={"Location": "https://test-bucket.s3.amazonaws.com/"}
    )
    result = await mock_client.create_bucket(
        acl="private",
        object_lock_enabled=True,
        object_ownership="BucketOwnerPreferred",
    )

    assert len(mock_client.requests) == 1
    call_args = mock_client.requests[0]

    assert call_args["method"] == "PUT"
    assert call_args.get("key") is None
    headers = call_args["headers"]
    assert headers["x-amz-acl"] == "private"
    assert headers["x-amz-bucket-object-lock-enabled"] == "true"
    assert headers["x-amz-object-ownership"] == "BucketOwnerPreferred"
    assert call_args.get("params") is None
    assert call_args.get("data") is None

    assert result["location"] == "https://test-bucket.s3.amazonaws.com/"


@pytest.mark.asyncio
async def test_create_bucket_with_grant_headers(mock_client):
    mock_client.add_response(
        "", headers={"Location": "https://test-bucket.s3.amazonaws.com/"}
    )
    result = await mock_client.create_bucket(
        grant_full_control="id=canonical-user-id",
        grant_read="id=canonical-user-id",
        grant_read_acp="id=canonical-user-id",
        grant_write="id=canonical-user-id",
        grant_write_acp="id=canonical-user-id",
    )

    assert len(mock_client.requests) == 1
    call_args = mock_client.requests[0]

    assert call_args["method"] == "PUT"
    assert call_args.get("key") is None
    headers = call_args["headers"]
    assert headers["x-amz-grant-full-control"] == "id=canonical-user-id"
    assert headers["x-amz-grant-read"] == "id=canonical-user-id"
    assert headers["x-amz-grant-read-acp"] == "id=canonical-user-id"
    assert headers["x-amz-grant-write"] == "id=canonical-user-id"
    assert headers["x-amz-grant-write-acp"] == "id=canonical-user-id"
    assert call_args.get("params") is None
    assert call_args.get("data") is None

    assert result["location"] == "https://test-bucket.s3.amazonaws.com/"


@pytest.mark.asyncio
async def test_create_bucket_directory_bucket_with_location(mock_client):
    mock_client.add_response(
        "",
        headers={
            "Location": "https://test-bucket--use1-az1--x-s3.s3express-use1-az1.us-east-1.amazonaws.com/"
        },
    )
    result = await mock_client.create_bucket(
        location_name="use1-az1",
        location_type="AvailabilityZone",
        bucket_type="Directory",
        data_redundancy="SingleAvailabilityZone",
    )

    assert len(mock_client.requests) == 1
    call_args = mock_client.requests[0]

    assert call_args["method"] == "PUT"
    # bucket is no longer passed to _make_request
    assert call_args.get("key") is None
    assert call_args["headers"]["Content-Type"] == "application/xml"
    assert call_args.get("params") is None

    # Check that the XML body contains the Location and Bucket elements
    data = call_args["data"].decode("utf-8")
    assert "<Location>" in data
    assert "<Name>use1-az1</Name>" in data
    assert "<Type>AvailabilityZone</Type>" in data
    assert "<Bucket>" in data
    assert "<DataRedundancy>SingleAvailabilityZone</DataRedundancy>" in data
    assert "<Type>Directory</Type>" in data
    assert "CreateBucketConfiguration" in data

    assert (
        result["location"]
        == "https://test-bucket--use1-az1--x-s3.s3express-use1-az1.us-east-1.amazonaws.com/"
    )


@pytest.mark.asyncio
async def test_create_bucket_mixed_configuration(mock_client):
    mock_client.add_response(
        "", headers={"Location": "https://test-bucket.s3.eu-west-1.amazonaws.com/"}
    )
    result = await mock_client.create_bucket(
        region="eu-west-1",
        acl="private",
        grant_full_control="id=canonical-user-id",
        object_lock_enabled=True,
        object_ownership="BucketOwnerPreferred",
    )

    assert len(mock_client.requests) == 1
    call_args = mock_client.requests[0]

    assert call_args["method"] == "PUT"
    # bucket is no longer passed to _make_request
    assert call_args.get("key") is None
    headers = call_args["headers"]
    assert headers["x-amz-acl"] == "private"
    assert headers["x-amz-grant-full-control"] == "id=canonical-user-id"
    assert headers["x-amz-bucket-object-lock-enabled"] == "true"
    assert headers["x-amz-object-ownership"] == "BucketOwnerPreferred"
    assert headers["Content-Type"] == "application/xml"
    assert call_args.get("params") is None

    # Check that the XML body contains the LocationConstraint
    data = call_args["data"].decode("utf-8")
    assert "<LocationConstraint>eu-west-1</LocationConstraint>" in data
    assert "CreateBucketConfiguration" in data

    assert result["location"] == "https://test-bucket.s3.eu-west-1.amazonaws.com/"
