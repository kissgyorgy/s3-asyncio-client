"""Unit tests for multipart upload functionality."""

from unittest.mock import AsyncMock, Mock

import pytest

from s3_asyncio_client import S3Client
from s3_asyncio_client.exceptions import S3ClientError
from s3_asyncio_client.multipart import MultipartUpload


@pytest.mark.asyncio
async def test_create_multipart_upload():
    """Test creating a multipart upload."""
    client = S3Client("test-key", "test-secret", "us-east-1")

    # Mock XML response for initiate multipart upload
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <InitiateMultipartUploadResult>
        <Bucket>test-bucket</Bucket>
        <Key>test-key</Key>
        <UploadId>upload123</UploadId>
    </InitiateMultipartUploadResult>"""

    mock_response = Mock()
    mock_response.text = AsyncMock(return_value=xml_response)

    client._make_request = AsyncMock(return_value=mock_response)

    multipart = await client.create_multipart_upload(
        bucket="test-bucket",
        key="large-file.bin",
        content_type="application/octet-stream",
        metadata={"author": "test"},
    )

    # Check that request was made correctly
    client._make_request.assert_called_once_with(
        method="POST",
        bucket="test-bucket",
        key="large-file.bin",
        headers={
            "Content-Type": "application/octet-stream",
            "x-amz-meta-author": "test",
        },
        params={"uploads": ""},
    )

    # Check multipart object
    assert isinstance(multipart, MultipartUpload)
    assert multipart.bucket == "test-bucket"
    assert multipart.key == "large-file.bin"
    assert multipart.upload_id == "upload123"


@pytest.mark.asyncio
async def test_multipart_upload_part():
    """Test uploading a part in multipart upload."""
    client = S3Client("test-key", "test-secret", "us-east-1")
    multipart = MultipartUpload(client, "test-bucket", "test-key", "upload123")

    # Mock response for upload part
    mock_response = Mock()
    mock_response.headers = {"ETag": '"part1etag"'}

    client._make_request = AsyncMock(return_value=mock_response)

    part_data = b"x" * (5 * 1024 * 1024)  # 5MB
    result = await multipart.upload_part(1, part_data)

    # Check request
    client._make_request.assert_called_once_with(
        method="PUT",
        bucket="test-bucket",
        key="test-key",
        headers={"Content-Length": str(len(part_data))},
        params={"partNumber": "1", "uploadId": "upload123"},
        data=part_data,
    )

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
async def test_multipart_complete():
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

    mock_response = Mock()
    mock_response.text = AsyncMock(return_value=xml_response)

    client._make_request = AsyncMock(return_value=mock_response)

    result = await multipart.complete()

    # Check that completion request was made
    client._make_request.assert_called_once()
    call_args = client._make_request.call_args

    assert call_args[1]["method"] == "POST"
    assert call_args[1]["bucket"] == "test-bucket"
    assert call_args[1]["key"] == "test-key"
    assert call_args[1]["params"] == {"uploadId": "upload123"}

    # Check XML payload
    xml_data = call_args[1]["data"].decode()
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
async def test_multipart_abort():
    """Test aborting a multipart upload."""
    client = S3Client("test-key", "test-secret", "us-east-1")
    multipart = MultipartUpload(client, "test-bucket", "test-key", "upload123")

    # Add some parts
    multipart.parts = [{"part_number": 1, "etag": "etag1", "size": 5000000}]

    mock_response = Mock()
    client._make_request = AsyncMock(return_value=mock_response)

    await multipart.abort()

    # Check abort request
    client._make_request.assert_called_once_with(
        method="DELETE",
        bucket="test-bucket",
        key="test-key",
        params={"uploadId": "upload123"},
    )

    # Check that parts list is cleared
    assert len(multipart.parts) == 0


@pytest.mark.asyncio
async def test_upload_file_multipart_small_file():
    """Test multipart upload with file smaller than part size."""
    client = S3Client("test-key", "test-secret", "us-east-1")

    # Mock put_object for small file
    client.put_object = AsyncMock(return_value={"etag": "small-file-etag"})

    small_data = b"x" * 1000  # 1KB file
    result = await client.upload_file_multipart(
        bucket="test-bucket",
        key="small-file.txt",
        data=small_data,
    )

    # Should use regular put_object
    client.put_object.assert_called_once_with(
        bucket="test-bucket",
        key="small-file.txt",
        data=small_data,
        content_type=None,
        metadata=None,
    )

    assert result["etag"] == "small-file-etag"


@pytest.mark.asyncio
async def test_upload_file_multipart_large_file():
    """Test multipart upload with large file."""
    client = S3Client("test-key", "test-secret", "us-east-1")

    # Mock all the multipart operations
    mock_multipart = Mock()
    mock_multipart.upload_part = AsyncMock()
    mock_multipart.complete = AsyncMock(return_value={"etag": "large-file-etag"})
    mock_multipart.abort = AsyncMock()

    client.create_multipart_upload = AsyncMock(return_value=mock_multipart)

    # Create data larger than 5MB
    large_data = b"x" * (10 * 1024 * 1024)  # 10MB
    result = await client.upload_file_multipart(
        bucket="test-bucket",
        key="large-file.bin",
        data=large_data,
        part_size=5 * 1024 * 1024,
    )

    # Check multipart upload was created
    client.create_multipart_upload.assert_called_once_with(
        bucket="test-bucket",
        key="large-file.bin",
        content_type=None,
        metadata=None,
    )

    # Check parts were uploaded (10MB with 5MB parts = 2 parts)
    assert mock_multipart.upload_part.call_count == 2

    # Check first part (5MB)
    first_call = mock_multipart.upload_part.call_args_list[0]
    assert first_call[0][0] == 1  # part number
    assert len(first_call[0][1]) == 5 * 1024 * 1024  # part size

    # Check second part (5MB)
    second_call = mock_multipart.upload_part.call_args_list[1]
    assert second_call[0][0] == 2  # part number
    assert len(second_call[0][1]) == 5 * 1024 * 1024  # part size

    # Check completion
    mock_multipart.complete.assert_called_once()
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
