"""Tests for multipart upload functionality."""

import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from s3_asyncio_client.exceptions import S3ClientError
from s3_asyncio_client.multipart import (
    DEFAULT_MULTIPART_CHUNKSIZE,
    DEFAULT_MULTIPART_THRESHOLD,
    MAX_PARTS,
    MIN_PART_SIZE,
    TransferConfig,
    abort_multipart_upload,
    adjust_chunk_size,
    calculate_file_size,
    complete_multipart_upload,
    create_multipart_upload,
    read_file_chunks,
    read_fileobj_chunks,
    should_use_multipart,
    upload_file,
    upload_part,
)


class TestTransferConfig:
    """Test TransferConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = TransferConfig()
        assert config.multipart_threshold == DEFAULT_MULTIPART_THRESHOLD
        assert config.multipart_chunksize == DEFAULT_MULTIPART_CHUNKSIZE
        assert config.max_concurrency == 10

    def test_custom_config(self):
        """Test custom configuration values."""
        config = TransferConfig(
            multipart_threshold=16 * 1024 * 1024,
            multipart_chunksize=16 * 1024 * 1024,
            max_concurrency=5,
        )
        assert config.multipart_threshold == 16 * 1024 * 1024
        assert config.multipart_chunksize == 16 * 1024 * 1024
        assert config.max_concurrency == 5


class TestUploadDecision:
    """Test upload strategy decision logic."""

    def test_should_use_multipart_true(self):
        """Test multipart decision for large files."""
        # File larger than threshold should use multipart
        assert should_use_multipart(10 * 1024 * 1024, 8 * 1024 * 1024) is True

    def test_should_use_multipart_false(self):
        """Test single-part decision for small files."""
        # File smaller than threshold should use single-part
        assert should_use_multipart(5 * 1024 * 1024, 8 * 1024 * 1024) is False

    def test_should_use_multipart_exact_threshold(self):
        """Test decision when file size equals threshold."""
        # File equal to threshold should use single-part
        assert should_use_multipart(8 * 1024 * 1024, 8 * 1024 * 1024) is False


class TestChunkSizeAdjustment:
    """Test chunk size calculation and adjustment."""

    def test_adjust_chunk_size_within_limits(self):
        """Test chunk size adjustment when within limits."""
        # Chunk size within limits should remain unchanged
        chunksize = 8 * 1024 * 1024  # 8MB
        assert adjust_chunk_size(chunksize) == chunksize

    def test_adjust_chunk_size_too_small(self):
        """Test chunk size adjustment when too small."""
        # Chunk size below minimum should be increased
        chunksize = 1 * 1024 * 1024  # 1MB (below 5MB minimum)
        assert adjust_chunk_size(chunksize) == MIN_PART_SIZE

    def test_adjust_chunk_size_for_max_parts(self):
        """Test chunk size adjustment to avoid exceeding max parts."""
        # Large file that would require too many parts
        file_size = 100 * 1024 * 1024 * 1024  # 100GB
        small_chunksize = 5 * 1024 * 1024  # 5MB

        adjusted = adjust_chunk_size(small_chunksize, file_size)
        num_parts = file_size // adjusted + (1 if file_size % adjusted else 0)

        assert num_parts <= MAX_PARTS
        assert adjusted >= MIN_PART_SIZE


class TestFileSize:
    """Test file size calculation."""

    def test_calculate_file_size_path(self):
        """Test file size calculation from file path."""
        with tempfile.NamedTemporaryFile() as tmp:
            data = b"test data" * 1000
            tmp.write(data)
            tmp.flush()

            size = calculate_file_size(tmp.name)
            assert size == len(data)

    def test_calculate_file_size_pathlib(self):
        """Test file size calculation from pathlib.Path."""
        with tempfile.NamedTemporaryFile() as tmp:
            data = b"test data" * 1000
            tmp.write(data)
            tmp.flush()

            size = calculate_file_size(Path(tmp.name))
            assert size == len(data)

    def test_calculate_file_size_fileobj(self):
        """Test file size calculation from file-like object."""
        data = b"test data" * 1000
        fileobj = BytesIO(data)

        size = calculate_file_size(fileobj)
        assert size == len(data)
        # Position should be restored
        assert fileobj.tell() == 0

    def test_calculate_file_size_unsupported(self):
        """Test file size calculation with unsupported object."""
        with pytest.raises(S3ClientError, match="Cannot determine size"):
            calculate_file_size("not a valid file object")


class TestFileReading:
    """Test async file reading functionality."""

    @pytest.mark.asyncio
    async def test_read_file_chunks(self):
        """Test reading file chunks from file path."""
        with tempfile.NamedTemporaryFile() as tmp:
            data = b"0123456789" * 100  # 1000 bytes
            tmp.write(data)
            tmp.flush()

            chunks = []
            async for chunk in read_file_chunks(tmp.name, 300):
                chunks.append(chunk)

            # Should have 4 chunks: 300, 300, 300, 100
            assert len(chunks) == 4
            assert len(chunks[0]) == 300
            assert len(chunks[1]) == 300
            assert len(chunks[2]) == 300
            assert len(chunks[3]) == 100
            assert b"".join(chunks) == data

    @pytest.mark.asyncio
    async def test_read_fileobj_chunks(self):
        """Test reading file chunks from file-like object."""
        data = b"0123456789" * 100  # 1000 bytes
        fileobj = BytesIO(data)

        chunks = []
        async for chunk in read_fileobj_chunks(fileobj, 300):
            chunks.append(chunk)

        # Should have 4 chunks: 300, 300, 300, 100
        assert len(chunks) == 4
        assert len(chunks[0]) == 300
        assert len(chunks[1]) == 300
        assert len(chunks[2]) == 300
        assert len(chunks[3]) == 100
        assert b"".join(chunks) == data


class TestMultipartOperations:
    """Test core multipart S3 operations."""

    @pytest.mark.asyncio
    async def test_create_multipart_upload(self):
        """Test creating a multipart upload."""
        mock_client = MagicMock()
        mock_response = AsyncMock()
        mock_response.text.return_value = """
        <InitiateMultipartUploadResult>
            <UploadId>test-upload-id</UploadId>
        </InitiateMultipartUploadResult>
        """
        mock_client._make_request = AsyncMock(return_value=mock_response)

        upload_id = await create_multipart_upload(
            mock_client, "test-bucket", "test-key"
        )

        assert upload_id == "test-upload-id"
        mock_client._make_request.assert_called_once()
        mock_response.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_multipart_upload_with_metadata(self):
        """Test creating multipart upload with metadata."""
        mock_client = MagicMock()
        mock_response = AsyncMock()
        mock_response.text.return_value = """
        <InitiateMultipartUploadResult>
            <UploadId>test-upload-id</UploadId>
        </InitiateMultipartUploadResult>
        """
        mock_client._make_request = AsyncMock(return_value=mock_response)

        upload_id = await create_multipart_upload(
            mock_client,
            "test-bucket",
            "test-key",
            content_type="application/octet-stream",
            metadata={"test": "value"},
        )

        assert upload_id == "test-upload-id"
        # Check that headers were set correctly
        call_args = mock_client._make_request.call_args
        headers = call_args[1]["headers"]
        assert headers["Content-Type"] == "application/octet-stream"
        assert headers["x-amz-meta-test"] == "value"

    @pytest.mark.asyncio
    async def test_upload_part(self):
        """Test uploading a single part."""
        mock_client = MagicMock()
        mock_response = AsyncMock()
        mock_response.headers = {"ETag": '"test-etag"'}
        mock_client._make_request = AsyncMock(return_value=mock_response)

        data = b"test data"
        result = await upload_part(
            mock_client, "test-bucket", "test-key", "upload-id", 1, data
        )

        assert result == {
            "part_number": 1,
            "etag": "test-etag",
            "size": len(data),
        }
        mock_response.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_part_invalid_number(self):
        """Test upload part with invalid part number."""
        mock_client = MagicMock()

        with pytest.raises(S3ClientError, match="Part number must be between"):
            await upload_part(mock_client, "bucket", "key", "id", 0, b"data")

        with pytest.raises(S3ClientError, match="Part number must be between"):
            await upload_part(
                mock_client, "bucket", "key", "id", MAX_PARTS + 1, b"data"
            )

    @pytest.mark.asyncio
    async def test_complete_multipart_upload(self):
        """Test completing a multipart upload."""
        mock_client = MagicMock()
        mock_response = AsyncMock()
        mock_response.text.return_value = """
        <CompleteMultipartUploadResult>
            <Location>https://bucket.s3.amazonaws.com/key</Location>
            <ETag>"final-etag"</ETag>
        </CompleteMultipartUploadResult>
        """
        mock_client._make_request = AsyncMock(return_value=mock_response)

        parts = [
            {"part_number": 1, "etag": "etag1"},
            {"part_number": 2, "etag": "etag2"},
        ]

        result = await complete_multipart_upload(
            mock_client, "test-bucket", "test-key", "upload-id", parts
        )

        assert result["location"] == "https://bucket.s3.amazonaws.com/key"
        assert result["etag"] == "final-etag"
        assert result["parts_count"] == 2
        mock_response.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_multipart_upload_no_parts(self):
        """Test completing multipart upload with no parts."""
        mock_client = MagicMock()

        with pytest.raises(S3ClientError, match="No parts to complete"):
            await complete_multipart_upload(
                mock_client, "bucket", "key", "upload-id", []
            )

    @pytest.mark.asyncio
    async def test_abort_multipart_upload(self):
        """Test aborting a multipart upload."""
        mock_client = MagicMock()
        mock_response = AsyncMock()
        mock_client._make_request = AsyncMock(return_value=mock_response)

        await abort_multipart_upload(
            mock_client, "test-bucket", "test-key", "upload-id"
        )

        mock_client._make_request.assert_called_once()
        mock_response.close.assert_called_once()


class TestUploadFile:
    """Test the main upload_file function."""

    @pytest.mark.asyncio
    async def test_upload_file_single_part(self):
        """Test upload_file chooses single-part for small files."""
        mock_client = MagicMock()
        mock_client.put_object = AsyncMock(return_value={"etag": "test-etag"})

        with tempfile.NamedTemporaryFile() as tmp:
            data = b"small file data"
            tmp.write(data)
            tmp.flush()

            config = TransferConfig(multipart_threshold=1024)  # 1KB threshold

            result = await upload_file(
                mock_client, "test-bucket", "test-key", tmp.name, config
            )

            assert result["upload_type"] == "single_part"
            assert result["size"] == len(data)
            mock_client.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_file_multipart(self):
        """Test upload_file chooses multipart for large files."""
        mock_client = MagicMock()

        # Mock multipart operations
        with (
            patch("s3_asyncio_client.multipart.create_multipart_upload") as mock_create,
            patch(
                "s3_asyncio_client.multipart._upload_parts_concurrently"
            ) as mock_upload_parts,
            patch(
                "s3_asyncio_client.multipart.complete_multipart_upload"
            ) as mock_complete,
        ):
            mock_create.return_value = "test-upload-id"
            mock_upload_parts.return_value = [
                {"part_number": 1, "etag": "etag1"},
                {"part_number": 2, "etag": "etag2"},
            ]
            mock_complete.return_value = {
                "location": "test-location",
                "etag": "final-etag",
                "parts_count": 2,
            }

            with tempfile.NamedTemporaryFile() as tmp:
                data = b"0" * (10 * 1024 * 1024)  # 10MB file
                tmp.write(data)
                tmp.flush()

                config = TransferConfig(
                    multipart_threshold=5 * 1024 * 1024
                )  # 5MB threshold

                result = await upload_file(
                    mock_client, "test-bucket", "test-key", tmp.name, config
                )

                assert result["upload_type"] == "multipart"
                assert result["size"] == len(data)
                assert result["parts_count"] == 2
                mock_create.assert_called_once()
                mock_upload_parts.assert_called_once()
                mock_complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_file_with_fileobj(self):
        """Test upload_file with file-like object."""
        mock_client = MagicMock()
        mock_client.put_object = AsyncMock(return_value={"etag": "test-etag"})

        data = b"file object data"
        fileobj = BytesIO(data)

        config = TransferConfig(multipart_threshold=1024)  # 1KB threshold

        result = await upload_file(
            mock_client, "test-bucket", "test-key", fileobj, config
        )

        assert result["upload_type"] == "single_part"
        assert result["size"] == len(data)
        mock_client.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_file_with_progress_callback(self):
        """Test upload_file with progress callback."""
        mock_client = MagicMock()
        mock_client.put_object = AsyncMock(return_value={"etag": "test-etag"})

        progress_calls = []

        def progress_callback(bytes_transferred):
            progress_calls.append(bytes_transferred)

        with tempfile.NamedTemporaryFile() as tmp:
            data = b"test data with progress"
            tmp.write(data)
            tmp.flush()

            config = TransferConfig(multipart_threshold=1024)  # 1KB threshold

            await upload_file(
                mock_client,
                "test-bucket",
                "test-key",
                tmp.name,
                config,
                progress_callback=progress_callback,
            )

            assert len(progress_calls) == 1
            assert progress_calls[0] == len(data)

    @pytest.mark.asyncio
    async def test_upload_file_multipart_error_cleanup(self):
        """Test that multipart upload aborts on error."""
        mock_client = MagicMock()

        with (
            patch("s3_asyncio_client.multipart.create_multipart_upload") as mock_create,
            patch(
                "s3_asyncio_client.multipart._upload_parts_concurrently"
            ) as mock_upload_parts,
            patch("s3_asyncio_client.multipart.abort_multipart_upload") as mock_abort,
        ):
            mock_create.return_value = "test-upload-id"
            mock_upload_parts.side_effect = Exception("Upload failed")

            with tempfile.NamedTemporaryFile() as tmp:
                data = b"0" * (10 * 1024 * 1024)  # 10MB file
                tmp.write(data)
                tmp.flush()

                config = TransferConfig(multipart_threshold=5 * 1024 * 1024)

                with pytest.raises(Exception, match="Upload failed"):
                    await upload_file(
                        mock_client, "test-bucket", "test-key", tmp.name, config
                    )

                # Should have attempted to abort the upload
                mock_abort.assert_called_once_with(
                    mock_client, "test-bucket", "test-key", "test-upload-id"
                )
