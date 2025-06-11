"""Tests for S3 exceptions."""

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
    """Test basic S3Error functionality."""
    error = S3Error("Test error")
    assert str(error) == "Test error"
    assert error.message == "Test error"
    assert error.status_code is None
    assert error.error_code is None


def test_s3_error_with_status_code():
    """Test S3Error with status code."""
    error = S3Error("Test error", status_code=500)
    assert str(error) == "HTTP 500: Test error"
    assert error.status_code == 500


def test_s3_error_with_error_code():
    """Test S3Error with both status code and error code."""
    error = S3Error("Test error", status_code=404, error_code="NoSuchKey")
    assert str(error) == "NoSuchKey (404): Test error"
    assert error.error_code == "NoSuchKey"


def test_s3_client_error():
    """Test S3ClientError inherits from S3Error."""
    error = S3ClientError("Client error", status_code=400)
    assert isinstance(error, S3Error)
    assert str(error) == "HTTP 400: Client error"


def test_s3_server_error():
    """Test S3ServerError inherits from S3Error."""
    error = S3ServerError("Server error", status_code=500)
    assert isinstance(error, S3Error)
    assert str(error) == "HTTP 500: Server error"


def test_s3_not_found_error():
    """Test S3NotFoundError with default message."""
    error = S3NotFoundError()
    assert isinstance(error, S3ClientError)
    assert error.status_code == 404
    assert error.error_code == "NoSuchKey"
    assert "not found" in str(error).lower()


def test_s3_not_found_error_custom_message():
    """Test S3NotFoundError with custom message."""
    error = S3NotFoundError("Custom not found message")
    assert error.message == "Custom not found message"
    assert error.status_code == 404


def test_s3_access_denied_error():
    """Test S3AccessDeniedError with default message."""
    error = S3AccessDeniedError()
    assert isinstance(error, S3ClientError)
    assert error.status_code == 403
    assert error.error_code == "AccessDenied"
    assert "access denied" in str(error).lower()


def test_s3_invalid_request_error():
    """Test S3InvalidRequestError with default message."""
    error = S3InvalidRequestError()
    assert isinstance(error, S3ClientError)
    assert error.status_code == 400
    assert error.error_code == "InvalidRequest"
    assert "invalid request" in str(error).lower()


def test_exception_inheritance():
    """Test that all exceptions inherit properly."""
    assert issubclass(S3ClientError, S3Error)
    assert issubclass(S3ServerError, S3Error)
    assert issubclass(S3NotFoundError, S3ClientError)
    assert issubclass(S3AccessDeniedError, S3ClientError)
    assert issubclass(S3InvalidRequestError, S3ClientError)


def test_exception_can_be_raised():
    """Test that exceptions can be raised and caught."""
    with pytest.raises(S3Error):
        raise S3Error("Test")

    with pytest.raises(S3ClientError):
        raise S3ClientError("Test")

    with pytest.raises(S3NotFoundError):
        raise S3NotFoundError("Test")
