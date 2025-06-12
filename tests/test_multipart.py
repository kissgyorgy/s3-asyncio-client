"""Unit tests for multipart upload functionality."""

import pytest

from s3_asyncio_client import S3Client
from s3_asyncio_client.exceptions import S3ClientError
from s3_asyncio_client.multipart import MultipartUpload


@pytest.mark.asyncio
async def test_create_multipart_upload(monkeypatch):
    """Test creating a multipart upload."""
    client = S3Client("test-key", "test-secret", "us-east-1")

    # Mock XML response for initiate multipart upload
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <InitiateMultipartUploadResult>
        <Bucket>test-bucket</Bucket>
        <Key>test-key</Key>
        <UploadId>upload123</UploadId>
    </InitiateMultipartUploadResult>"""

    class MockResponse:
        async def text(self):
            return xml_response

        def close(self):
            pass

    mock_response = MockResponse()

    # Track calls to _make_request
    calls = []

    async def mock_make_request(**kwargs):
        calls.append(kwargs)
        return mock_response

    monkeypatch.setattr(client, "_make_request", mock_make_request)

    multipart = await client.create_multipart_upload(
        bucket="test-bucket",
        key="large-file.bin",
        content_type="application/octet-stream",
        metadata={"author": "test"},
    )

    # Check that request was made correctly
    assert len(calls) == 1
    assert calls[0] == {
        "method": "POST",
        "bucket": "test-bucket",
        "key": "large-file.bin",
        "headers": {
            "Content-Type": "application/octet-stream",
            "x-amz-meta-author": "test",
        },
        "params": {"uploads": ""},
    }

    # Check multipart object
    assert isinstance(multipart, MultipartUpload)
    assert multipart.bucket == "test-bucket"
    assert multipart.key == "large-file.bin"
    assert multipart.upload_id == "upload123"


@pytest.mark.asyncio
async def test_multipart_upload_part(monkeypatch):
    """Test uploading a part in multipart upload."""
    client = S3Client("test-key", "test-secret", "us-east-1")
    multipart = MultipartUpload(client, "test-bucket", "test-key", "upload123")

    # Mock response for upload part
    class MockResponse:
        headers = {"ETag": '"part1etag"'}

        def close(self):
            pass

    mock_response = MockResponse()

    # Track calls to _make_request
    calls = []

    async def mock_make_request(**kwargs):
        calls.append(kwargs)
        return mock_response

    monkeypatch.setattr(client, "_make_request", mock_make_request)

    part_data = b"x" * (5 * 1024 * 1024)  # 5MB
    result = await multipart.upload_part(1, part_data)

    # Check request
    assert len(calls) == 1
    assert calls[0] == {
        "method": "PUT",
        "bucket": "test-bucket",
        "key": "test-key",
        "headers": {"Content-Length": str(len(part_data))},
        "params": {"partNumber": "1", "uploadId": "upload123"},
        "data": part_data,
    }

    # Check result
    assert result["part_number"] == 1
    assert result["etag"] == "part1etag"
    assert result["size"] == len(part_data)

    # Check that part was added to multipart
    assert len(multipart.parts) == 1
    assert multipart.parts[0]["part_number"] == 1


@pytest.mark.asyncio
async def test_multipart_upload_invalid_part_number():
    """Test upload part with invalid part number."""
    client = S3Client("test-key", "test-secret", "us-east-1")
    multipart = MultipartUpload(client, "test-bucket", "test-key", "upload123")

    with pytest.raises(S3ClientError, match="Part number must be between 1 and 10000"):
        await multipart.upload_part(0, b"data")

    with pytest.raises(S3ClientError, match="Part number must be between 1 and 10000"):
        await multipart.upload_part(10001, b"data")


@pytest.mark.asyncio
async def test_multipart_complete(monkeypatch):
    """Test completing a multipart upload."""
    client = S3Client("test-key", "test-secret", "us-east-1")
    multipart = MultipartUpload(client, "test-bucket", "test-key", "upload123")

    # Add some parts manually
    multipart.parts = [
        {"part_number": 1, "etag": "etag1", "size": 5000000},
        {"part_number": 2, "etag": "etag2", "size": 3000000},
    ]

    # Mock completion response
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <CompleteMultipartUploadResult>
        <Location>https://test-bucket.s3.amazonaws.com/test-key</Location>
        <Bucket>test-bucket</Bucket>
        <Key>test-key</Key>
        <ETag>"final-etag"</ETag>
    </CompleteMultipartUploadResult>"""

    class MockResponse:
        async def text(self):
            return xml_response

        def close(self):
            pass

    mock_response = MockResponse()

    # Track calls to _make_request
    calls = []

    async def mock_make_request(**kwargs):
        calls.append(kwargs)
        return mock_response

    monkeypatch.setattr(client, "_make_request", mock_make_request)

    result = await multipart.complete()

    # Check that completion request was made
    assert len(calls) == 1
    call_args = calls[0]

    assert call_args["method"] == "POST"
    assert call_args["bucket"] == "test-bucket"
    assert call_args["key"] == "test-key"
    assert call_args["params"] == {"uploadId": "upload123"}

    # Check XML payload
    xml_data = call_args["data"].decode()
    assert "<CompleteMultipartUpload>" in xml_data
    assert "<PartNumber>1</PartNumber>" in xml_data
    assert '<ETag>"etag1"</ETag>' in xml_data
    assert "<PartNumber>2</PartNumber>" in xml_data

    # Check result
    assert result["location"] == "https://test-bucket.s3.amazonaws.com/test-key"
    assert result["etag"] == "final-etag"
    assert result["bucket"] == "test-bucket"
    assert result["key"] == "test-key"
    assert result["parts_count"] == 2


@pytest.mark.asyncio
async def test_multipart_complete_no_parts():
    """Test completing multipart upload with no parts."""
    client = S3Client("test-key", "test-secret", "us-east-1")
    multipart = MultipartUpload(client, "test-bucket", "test-key", "upload123")

    with pytest.raises(S3ClientError, match="No parts uploaded"):
        await multipart.complete()


@pytest.mark.asyncio
async def test_multipart_abort(monkeypatch):
    """Test aborting a multipart upload."""
    client = S3Client("test-key", "test-secret", "us-east-1")
    multipart = MultipartUpload(client, "test-bucket", "test-key", "upload123")

    # Add some parts
    multipart.parts = [{"part_number": 1, "etag": "etag1", "size": 5000000}]

    class MockResponse:
        def close(self):
            pass

    mock_response = MockResponse()

    # Track calls to _make_request
    calls = []

    async def mock_make_request(**kwargs):
        calls.append(kwargs)
        return mock_response

    monkeypatch.setattr(client, "_make_request", mock_make_request)

    await multipart.abort()

    # Check abort request
    assert len(calls) == 1
    assert calls[0] == {
        "method": "DELETE",
        "bucket": "test-bucket",
        "key": "test-key",
        "params": {"uploadId": "upload123"},
    }

    # Check that parts list is cleared
    assert len(multipart.parts) == 0


@pytest.mark.asyncio
async def test_upload_file_multipart_small_file(monkeypatch):
    """Test multipart upload with file smaller than part size."""
    client = S3Client("test-key", "test-secret", "us-east-1")

    # Mock put_object for small file
    calls = []

    async def mock_put_object(**kwargs):
        calls.append(kwargs)
        return {"etag": "small-file-etag"}

    monkeypatch.setattr(client, "put_object", mock_put_object)

    small_data = b"x" * 1000  # 1KB file
    result = await client.upload_file_multipart(
        bucket="test-bucket",
        key="small-file.txt",
        data=small_data,
    )

    # Should use regular put_object
    assert len(calls) == 1
    assert calls[0] == {
        "bucket": "test-bucket",
        "key": "small-file.txt",
        "data": small_data,
        "content_type": None,
        "metadata": None,
    }

    assert result["etag"] == "small-file-etag"


@pytest.mark.asyncio
async def test_upload_file_multipart_large_file(monkeypatch):
    """Test multipart upload with large file."""
    client = S3Client("test-key", "test-secret", "us-east-1")

    # Mock all the multipart operations
    upload_part_calls = []
    complete_calls = []
    abort_calls = []

    class MockMultipart:
        async def upload_part(self, part_number, data):
            upload_part_calls.append((part_number, data))

        async def complete(self):
            complete_calls.append(True)
            return {"etag": "large-file-etag"}

        async def abort(self):
            abort_calls.append(True)

    mock_multipart = MockMultipart()

    create_multipart_calls = []

    async def mock_create_multipart_upload(**kwargs):
        create_multipart_calls.append(kwargs)
        return mock_multipart

    monkeypatch.setattr(client, "create_multipart_upload", mock_create_multipart_upload)

    # Create data larger than 5MB
    large_data = b"x" * (10 * 1024 * 1024)  # 10MB
    result = await client.upload_file_multipart(
        bucket="test-bucket",
        key="large-file.bin",
        data=large_data,
        part_size=5 * 1024 * 1024,
    )

    # Check multipart upload was created
    assert len(create_multipart_calls) == 1
    assert create_multipart_calls[0] == {
        "bucket": "test-bucket",
        "key": "large-file.bin",
        "content_type": None,
        "metadata": None,
    }

    # Check parts were uploaded (10MB with 5MB parts = 2 parts)
    assert len(upload_part_calls) == 2

    # Check first part (5MB)
    first_call = upload_part_calls[0]
    assert first_call[0] == 1  # part number
    assert len(first_call[1]) == 5 * 1024 * 1024  # part size

    # Check second part (5MB)
    second_call = upload_part_calls[1]
    assert second_call[0] == 2  # part number
    assert len(second_call[1]) == 5 * 1024 * 1024  # part size

    # Check completion
    assert len(complete_calls) == 1
    assert result["etag"] == "large-file-etag"


@pytest.mark.asyncio
async def test_upload_file_multipart_invalid_part_size():
    """Test multipart upload with invalid part size."""
    client = S3Client("test-key", "test-secret", "us-east-1")

    with pytest.raises(S3ClientError, match="Part size must be at least 5MB"):
        await client.upload_file_multipart(
            bucket="test-bucket",
            key="file.bin",
            data=b"x" * 1000,
            part_size=1024,  # Too small
        )
