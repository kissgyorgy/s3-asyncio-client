import pytest

from s3_asyncio_client.exceptions import (
    S3AccessDeniedError,
    S3ClientError,
    S3Error,
    S3InvalidRequestError,
    S3NotFoundError,
    S3ServerError,
)


def test_s3_error_base():
    error = S3Error("Test error")
    assert str(error) == "Test error"
    assert error.message == "Test error"
    assert error.status_code is None
    assert error.error_code is None


def test_s3_error_with_status_code():
    error = S3Error("Test error", status_code=500)
    assert str(error) == "HTTP 500: Test error"
    assert error.status_code == 500


def test_s3_error_with_error_code():
    error = S3Error("Test error", status_code=404, error_code="NoSuchKey")
    assert str(error) == "NoSuchKey (404): Test error"
    assert error.error_code == "NoSuchKey"


def test_s3_client_error():
    error = S3ClientError("Client error", status_code=400)
    assert isinstance(error, S3Error)
    assert str(error) == "HTTP 400: Client error"


def test_s3_server_error():
    error = S3ServerError("Server error", status_code=500)
    assert isinstance(error, S3Error)
    assert str(error) == "HTTP 500: Server error"


def test_s3_not_found_error():
    error = S3NotFoundError()
    assert isinstance(error, S3ClientError)
    assert error.status_code == 404
    assert error.error_code == "NoSuchKey"
    assert "not found" in str(error).lower()


def test_s3_not_found_error_custom_message():
    error = S3NotFoundError("Custom not found message")
    assert error.message == "Custom not found message"
    assert error.status_code == 404


def test_s3_access_denied_error():
    error = S3AccessDeniedError()
    assert isinstance(error, S3ClientError)
    assert error.status_code == 403
    assert error.error_code == "AccessDenied"
    assert "access denied" in str(error).lower()


def test_s3_invalid_request_error():
    error = S3InvalidRequestError()
    assert isinstance(error, S3ClientError)
    assert error.status_code == 400
    assert error.error_code == "InvalidRequest"
    assert "invalid request" in str(error).lower()


def test_exception_inheritance():
    assert issubclass(S3ClientError, S3Error)
    assert issubclass(S3ServerError, S3Error)
    assert issubclass(S3NotFoundError, S3ClientError)
    assert issubclass(S3AccessDeniedError, S3ClientError)
    assert issubclass(S3InvalidRequestError, S3ClientError)


def test_exception_can_be_raised():
    with pytest.raises(S3Error):
        raise S3Error("Test")

    with pytest.raises(S3ClientError):
        raise S3ClientError("Test")

    with pytest.raises(S3NotFoundError):
        raise S3NotFoundError("Test")
