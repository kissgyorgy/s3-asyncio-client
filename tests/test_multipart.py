import tempfile
from io import BytesIO
from pathlib import Path

import pytest

from s3_asyncio_client.exceptions import S3ClientError
from s3_asyncio_client.multipart import (
    DEFAULT_MULTIPART_CHUNKSIZE,
    DEFAULT_MULTIPART_THRESHOLD,
    MAX_PARTS,
    MIN_PART_SIZE,
    TransferConfig,
    adjust_chunk_size,
    calculate_file_size,
    read_file_chunks,
    read_fileobj_chunks,
    should_use_multipart,
)


class TestTransferConfig:
    def test_default_config(self):
        config = TransferConfig()
        assert config.multipart_threshold == DEFAULT_MULTIPART_THRESHOLD
        assert config.multipart_chunksize == DEFAULT_MULTIPART_CHUNKSIZE
        assert config.max_concurrency == 10

    def test_custom_config(self):
        config = TransferConfig(
            multipart_threshold=16 * 1024 * 1024,
            multipart_chunksize=16 * 1024 * 1024,
            max_concurrency=5,
        )
        assert config.multipart_threshold == 16 * 1024 * 1024
        assert config.multipart_chunksize == 16 * 1024 * 1024
        assert config.max_concurrency == 5


class TestUploadDecision:
    def test_larger_than_threshold_should_use_multipart(self):
        assert should_use_multipart(10 * 1024 * 1024, 8 * 1024 * 1024) is True

    def test_smaller_than_threshold_use_single_part(self):
        assert should_use_multipart(5 * 1024 * 1024, 8 * 1024 * 1024) is False

    def test_exact_threshold_should_use_single_part(self):
        assert should_use_multipart(8 * 1024 * 1024, 8 * 1024 * 1024) is False


class TestChunkSizeAdjustment:
    def test_adjust_chunk_size_within_limits_remains_unchanged(self):
        chunksize = 8 * 1024 * 1024
        assert adjust_chunk_size(chunksize) == chunksize

    def test_adjust_chunk_size_too_small_should_be_increased(self):
        chunksize = 1 * 1024 * 1024
        assert adjust_chunk_size(chunksize) == MIN_PART_SIZE

    def test_adjust_chunk_size_that_would_require_too_many_parts_to_may_parts(self):
        file_size = 100 * 1024 * 1024 * 1024
        small_chunksize = 5 * 1024 * 1024

        adjusted = adjust_chunk_size(small_chunksize, file_size)
        num_parts = file_size // adjusted + (1 if file_size % adjusted else 0)

        assert num_parts <= MAX_PARTS
        assert adjusted >= MIN_PART_SIZE


class TestFileSize:
    def test_calculate_file_size_path(self):
        with tempfile.NamedTemporaryFile() as tmp:
            data = b"test data" * 1000
            tmp.write(data)
            tmp.flush()

            size = calculate_file_size(tmp.name)
            assert size == len(data)

    def test_calculate_file_size_pathlib(self):
        with tempfile.NamedTemporaryFile() as tmp:
            data = b"test data" * 1000
            tmp.write(data)
            tmp.flush()

            size = calculate_file_size(Path(tmp.name))
            assert size == len(data)

    def test_calculate_file_size_fileobj(self):
        data = b"test data" * 1000
        fileobj = BytesIO(data)

        size = calculate_file_size(fileobj)
        assert size == len(data)
        assert fileobj.tell() == 0

    def test_calculate_file_size_unsupported(self):
        with pytest.raises(S3ClientError, match="Cannot determine size"):
            calculate_file_size("not a valid file object")


class TestFileReading:
    @pytest.mark.asyncio
    async def test_read_file_chunks(self):
        with tempfile.NamedTemporaryFile() as tmp:
            data = b"0123456789" * 100
            tmp.write(data)
            tmp.flush()

            chunks = []
            async for chunk in read_file_chunks(tmp.name, 300):
                chunks.append(chunk)

            assert len(chunks) == 4
            assert len(chunks[0]) == 300
            assert len(chunks[1]) == 300
            assert len(chunks[2]) == 300
            assert len(chunks[3]) == 100
            assert b"".join(chunks) == data

    @pytest.mark.asyncio
    async def test_read_fileobj_chunks(self):
        data = b"0123456789" * 100
        fileobj = BytesIO(data)

        chunks = []
        async for chunk in read_fileobj_chunks(fileobj, 300):
            chunks.append(chunk)

        assert len(chunks) == 4
        assert len(chunks[0]) == 300
        assert len(chunks[1]) == 300
        assert len(chunks[2]) == 300
        assert len(chunks[3]) == 100
        assert b"".join(chunks) == data


class TestMultipartOperations:
    @pytest.mark.asyncio
    async def test_create_multipart_upload(self, mock_client):
        mock_client.add_response("""
            <InitiateMultipartUploadResult>
                <UploadId>test-upload-id</UploadId>
            </InitiateMultipartUploadResult>
        """)
        upload_id = await mock_client.create_multipart_upload("test-bucket", "test-key")
        assert upload_id == "test-upload-id"

    @pytest.mark.asyncio
    async def test_create_multipart_upload_with_metadata(self, mock_client):
        mock_client.add_response("""
        <InitiateMultipartUploadResult>
            <UploadId>test-upload-id</UploadId>
        </InitiateMultipartUploadResult>
        """)
        upload_id = await mock_client.create_multipart_upload(
            "test-key",
            content_type="application/octet-stream",
            metadata={"test": "value"},
        )

        assert upload_id == "test-upload-id"

        headers = mock_client.requests[0]["headers"]
        assert headers["Content-Type"] == "application/octet-stream"
        assert headers["x-amz-meta-test"] == "value"

    @pytest.mark.asyncio
    async def test_upload_part(self, mock_client):
        class MockResponse:
            headers = {"ETag": '"test-etag"'}

            def close(self):
                pass

        async def mock_make_request_with_response(
            method, key=None, headers=None, params=None, data=None
        ):
            return MockResponse()

        mock_client._make_request = mock_make_request_with_response

        data = b"test data"
        result = await mock_client.upload_part("test-key", "upload-id", 1, data)

        assert result == {
            "part_number": 1,
            "etag": "test-etag",
            "size": len(data),
        }

    @pytest.mark.asyncio
    async def test_upload_part_invalid_number(self, mock_client):
        with pytest.raises(S3ClientError, match="Part number must be between"):
            await mock_client.upload_part("key", "id", 0, b"data")

        with pytest.raises(S3ClientError, match="Part number must be between"):
            await mock_client.upload_part("key", "id", MAX_PARTS + 1, b"data")

    @pytest.mark.asyncio
    async def test_complete_multipart_upload(self, mock_client):
        xml_response = """
        <CompleteMultipartUploadResult>
            <Location>https://bucket.s3.amazonaws.com/key</Location>
            <ETag>"final-etag"</ETag>
        </CompleteMultipartUploadResult>
        """
        mock_client.add_response(xml_response)

        parts = [
            {"part_number": 1, "etag": "etag1"},
            {"part_number": 2, "etag": "etag2"},
        ]

        result = await mock_client.complete_multipart_upload(
            "test-key", "upload-id", parts
        )

        assert result["location"] == "https://bucket.s3.amazonaws.com/key"
        assert result["etag"] == "final-etag"
        assert result["parts_count"] == 2

    @pytest.mark.asyncio
    async def test_complete_multipart_upload_no_parts(self, mock_client):
        with pytest.raises(S3ClientError, match="No parts to complete"):
            await mock_client.complete_multipart_upload("key", "upload-id", [])

    @pytest.mark.asyncio
    async def test_abort_multipart_upload(self, mock_client):
        mock_client.add_response("")
        await mock_client.abort_multipart_upload("test-key", "upload-id")
        assert len(mock_client.requests) == 1


class TestUploadFile:
    @pytest.mark.asyncio
    async def test_upload_file_single_part(self, mock_client):
        data = b"small file data"
        mock_client.add_response(data, headers={"ETag": '"test-etag"'})

        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write(data)
            tmp.flush()

            config = TransferConfig(multipart_threshold=1024)
            result = await mock_client.upload_file("test-key", tmp.name, config)

            assert result["upload_type"] == "single_part"
            assert result["size"] == len(data)

    @pytest.mark.asyncio
    async def test_upload_file_multipart(self, mock_client, monkeypatch):
        # Mock the multipart upload methods
        async def mock_create_multipart_upload(
            key, content_type=None, metadata=None, **kwargs
        ):
            return "test-upload-id"

        async def mock_upload_parts_concurrently(
            key,
            upload_id,
            file_source,
            part_size,
            max_concurrency=10,
            progress_callback=None,
        ):
            return [
                {"part_number": 1, "etag": "etag1"},
                {"part_number": 2, "etag": "etag2"},
            ]

        async def mock_complete_multipart_upload(key, upload_id, parts):
            return {
                "location": "test-location",
                "etag": "final-etag",
                "parts_count": 2,
            }

        monkeypatch.setattr(
            mock_client, "create_multipart_upload", mock_create_multipart_upload
        )
        monkeypatch.setattr(
            mock_client, "_upload_parts_concurrently", mock_upload_parts_concurrently
        )
        monkeypatch.setattr(
            mock_client, "complete_multipart_upload", mock_complete_multipart_upload
        )

        with tempfile.NamedTemporaryFile() as tmp:
            data = b"0" * (10 * 1024 * 1024)
            tmp.write(data)
            tmp.flush()

            config = TransferConfig(multipart_threshold=5 * 1024 * 1024)

            result = await mock_client.upload_file("test-key", tmp.name, config)

            assert result["upload_type"] == "multipart"
            assert result["size"] == len(data)
            assert result["parts_count"] == 2

    @pytest.mark.asyncio
    async def test_upload_file_with_fileobj(self, mock_client):
        async def mock_put_object(key, data, **kwargs):
            return {"etag": "test-etag"}

        mock_client.put_object = mock_put_object

        data = b"file object data"
        fileobj = BytesIO(data)

        config = TransferConfig(multipart_threshold=1024)  # 1KB threshold

        result = await mock_client.upload_file("test-key", fileobj, config)

        assert result["upload_type"] == "single_part"
        assert result["size"] == len(data)

    @pytest.mark.asyncio
    async def test_upload_file_with_progress_callback(self, mock_client):
        async def mock_put_object(key, data, **kwargs):
            return {"etag": "test-etag"}

        mock_client.put_object = mock_put_object

        progress_calls = []

        def progress_callback(bytes_transferred):
            progress_calls.append(bytes_transferred)

        with tempfile.NamedTemporaryFile() as tmp:
            data = b"test data with progress"
            tmp.write(data)
            tmp.flush()

            config = TransferConfig(multipart_threshold=1024)

            await mock_client.upload_file(
                "test-key",
                tmp.name,
                config,
                progress_callback=progress_callback,
            )

            assert len(progress_calls) == 1
            assert progress_calls[0] == len(data)

    @pytest.mark.asyncio
    async def test_upload_file_multipart_error_cleanup(self, mock_client, monkeypatch):
        # Track calls to abort_multipart_upload
        abort_calls = []

        async def mock_create_multipart_upload(
            key, content_type=None, metadata=None, **kwargs
        ):
            return "test-upload-id"

        async def mock_upload_parts_concurrently(
            key,
            upload_id,
            file_source,
            part_size,
            max_concurrency=10,
            progress_callback=None,
        ):
            raise Exception("Upload failed")

        async def mock_abort_multipart_upload(key, upload_id):
            abort_calls.append((key, upload_id))

        monkeypatch.setattr(
            mock_client, "create_multipart_upload", mock_create_multipart_upload
        )
        monkeypatch.setattr(
            mock_client, "_upload_parts_concurrently", mock_upload_parts_concurrently
        )
        monkeypatch.setattr(
            mock_client, "abort_multipart_upload", mock_abort_multipart_upload
        )

        with tempfile.NamedTemporaryFile() as tmp:
            data = b"0" * (10 * 1024 * 1024)
            tmp.write(data)
            tmp.flush()

            config = TransferConfig(multipart_threshold=5 * 1024 * 1024)

            with pytest.raises(Exception, match="Upload failed"):
                await mock_client.upload_file("test-key", tmp.name, config)

            assert len(abort_calls) == 1
            assert abort_calls[0] == ("test-key", "test-upload-id")
