"""End-to-end tests with local minio instance.

These tests assume a local minio server is running at http://localhost:9000
with default credentials (minioadmin/minioadmin).

Note: Some tests involving query parameters (like list with prefix) currently
fail due to signature calculation issues. Core functionality (put, get, head,
delete, multipart) works correctly.
"""

import tempfile
from pathlib import Path

import pytest

from s3_asyncio_client import S3Client


@pytest.fixture
def test_bucket():
    """Test bucket name for E2E tests."""
    return "e2e-test-bucket"


@pytest.fixture
async def minio_client():
    """S3Client configured for local minio instance."""
    client = S3Client(
        access_key="minioadmin",
        secret_key="minioadmin",
        region="us-east-1",
        endpoint_url="http://localhost:9000",
    )
    async with client:
        yield client


@pytest.fixture
def test_files():
    """Pre-generated test files with different content types."""
    files = {}

    # Create temporary directory for test files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Text file
        text_file = temp_path / "test.txt"
        text_file.write_text("Hello, S3 E2E Test!\nThis is a text file.")
        files["text"] = {
            "path": str(text_file),
            "content": text_file.read_bytes(),
            "content_type": "text/plain",
        }

        # JSON file
        json_file = temp_path / "data.json"
        json_content = '{"name": "test", "value": 42, "array": [1, 2, 3]}'
        json_file.write_text(json_content)
        files["json"] = {
            "path": str(json_file),
            "content": json_file.read_bytes(),
            "content_type": "application/json",
        }

        # Binary file (small image-like data)
        binary_file = temp_path / "binary.dat"
        binary_content = bytes([i % 256 for i in range(1024)])  # 1KB of test data
        binary_file.write_bytes(binary_content)
        files["binary"] = {
            "path": str(binary_file),
            "content": binary_content,
            "content_type": "application/octet-stream",
        }

        # Large file for multipart testing (5MB)
        large_file = temp_path / "large.bin"
        large_content = b"Large file content block!\n" * (5 * 1024 * 1024 // 25)
        large_file.write_bytes(large_content)
        files["large"] = {
            "path": str(large_file),
            "content": large_content,
            "content_type": "application/octet-stream",
        }

        yield files


@pytest.fixture(autouse=True)
async def ensure_test_bucket(minio_client, test_bucket):
    """Ensure test bucket exists and is clean before each test."""
    # Clean up any existing objects if bucket exists
    try:
        result = await minio_client.list_objects(test_bucket, max_keys=1000)
        for obj in result["objects"]:
            await minio_client.delete_object(test_bucket, obj["key"])
    except Exception:
        # Bucket doesn't exist or other error, which is fine
        # minio will auto-create buckets on first put
        pass


@pytest.mark.asyncio
async def test_put_get_text_file(minio_client, test_bucket, test_files):
    """Test uploading and downloading a text file."""
    file_info = test_files["text"]
    key = "test-files/hello.txt"

    # Upload file
    result = await minio_client.put_object(
        bucket=test_bucket,
        key=key,
        data=file_info["content"],
        content_type=file_info["content_type"],
        metadata={"author": "pytest", "test": "e2e"},
    )

    assert "etag" in result
    assert result["etag"]  # ETag should not be empty

    # Download file
    download_result = await minio_client.get_object(bucket=test_bucket, key=key)

    assert download_result["body"] == file_info["content"]
    assert download_result["content_type"] == file_info["content_type"]
    assert download_result["metadata"]["author"] == "pytest"
    assert download_result["metadata"]["test"] == "e2e"


@pytest.mark.asyncio
async def test_put_get_json_file(minio_client, test_bucket, test_files):
    """Test uploading and downloading a JSON file."""
    file_info = test_files["json"]
    key = "test-files/data.json"

    # Upload file
    await minio_client.put_object(
        bucket=test_bucket,
        key=key,
        data=file_info["content"],
        content_type=file_info["content_type"],
    )

    # Download file
    download_result = await minio_client.get_object(bucket=test_bucket, key=key)

    assert download_result["body"] == file_info["content"]
    assert download_result["content_type"] == file_info["content_type"]

    # Verify JSON content
    import json

    parsed_json = json.loads(download_result["body"].decode())
    assert parsed_json["name"] == "test"
    assert parsed_json["value"] == 42


@pytest.mark.asyncio
async def test_put_get_binary_file(minio_client, test_bucket, test_files):
    """Test uploading and downloading a binary file."""
    file_info = test_files["binary"]
    key = "test-files/binary.dat"

    # Upload file
    await minio_client.put_object(
        bucket=test_bucket,
        key=key,
        data=file_info["content"],
        content_type=file_info["content_type"],
    )

    # Download file
    download_result = await minio_client.get_object(bucket=test_bucket, key=key)

    assert download_result["body"] == file_info["content"]
    assert download_result["content_type"] == file_info["content_type"]
    assert len(download_result["body"]) == 1024


@pytest.mark.asyncio
async def test_head_object(minio_client, test_bucket, test_files):
    """Test getting object metadata without downloading."""
    file_info = test_files["text"]
    key = "test-files/metadata-test.txt"

    # Upload file with metadata
    await minio_client.put_object(
        bucket=test_bucket,
        key=key,
        data=file_info["content"],
        content_type=file_info["content_type"],
        metadata={"description": "Head test file", "version": "1.0"},
    )

    # Get metadata
    head_result = await minio_client.head_object(bucket=test_bucket, key=key)

    assert head_result["content_type"] == file_info["content_type"]
    assert head_result["content_length"] == len(file_info["content"])
    assert head_result["metadata"]["description"] == "Head test file"
    assert head_result["metadata"]["version"] == "1.0"


@pytest.mark.asyncio
async def test_list_objects(minio_client, test_bucket, test_files):
    """Test listing objects with different prefixes."""
    # Upload multiple files
    files_to_upload = [
        ("docs/readme.txt", test_files["text"]),
        ("docs/api.json", test_files["json"]),
        ("images/photo.dat", test_files["binary"]),
        ("config/settings.txt", test_files["text"]),
    ]

    for key, file_info in files_to_upload:
        await minio_client.put_object(
            bucket=test_bucket,
            key=key,
            data=file_info["content"],
            content_type=file_info["content_type"],
        )

    # List all objects
    all_objects = await minio_client.list_objects(bucket=test_bucket)
    assert len(all_objects["objects"]) == 4

    # List with prefix
    docs_objects = await minio_client.list_objects(bucket=test_bucket, prefix="docs/")
    assert len(docs_objects["objects"]) == 2

    # Verify object details
    for obj in docs_objects["objects"]:
        assert obj["key"].startswith("docs/")
        assert obj["size"] > 0
        assert "last_modified" in obj


@pytest.mark.asyncio
async def test_multipart_upload(minio_client, test_bucket, test_files):
    """Test multipart upload with a large file."""
    file_info = test_files["large"]
    key = "large-files/big-file.bin"

    # Create multipart upload
    multipart = await minio_client.create_multipart_upload(
        bucket=test_bucket,
        key=key,
        content_type=file_info["content_type"],
        metadata={"size": "large", "test": "multipart"},
    )

    # Upload parts (split into 5MB+ chunks - minimum for S3)
    chunk_size = 5 * 1024 * 1024  # 5MB minimum for multipart parts
    content = file_info["content"]

    part_number = 1
    for i in range(0, len(content), chunk_size):
        chunk = content[i : i + chunk_size]
        await multipart.upload_part(part_number, chunk)
        part_number += 1

    # Complete multipart upload
    completion_result = await multipart.complete()

    assert "etag" in completion_result
    assert "location" in completion_result

    # Verify the uploaded file
    download_result = await minio_client.get_object(bucket=test_bucket, key=key)
    assert download_result["body"] == file_info["content"]
    assert download_result["metadata"]["size"] == "large"
    assert download_result["metadata"]["test"] == "multipart"


@pytest.mark.asyncio
async def test_delete_object(minio_client, test_bucket, test_files):
    """Test deleting objects."""
    file_info = test_files["text"]
    key = "temp/delete-me.txt"

    # Upload file
    await minio_client.put_object(
        bucket=test_bucket,
        key=key,
        data=file_info["content"],
        content_type=file_info["content_type"],
    )

    # Verify file exists
    head_result = await minio_client.head_object(bucket=test_bucket, key=key)
    assert head_result["content_length"] == len(file_info["content"])

    # Delete file
    delete_result = await minio_client.delete_object(bucket=test_bucket, key=key)
    assert isinstance(delete_result, dict)

    # Verify file is gone
    with pytest.raises(Exception):  # Should raise S3NotFoundError
        await minio_client.head_object(bucket=test_bucket, key=key)


@pytest.mark.asyncio
async def test_file_upload_download_cycle(minio_client, test_bucket, test_files):
    """Test complete upload/download cycle for all file types."""
    uploaded_files = []

    # Upload all test files
    for file_type, file_info in test_files.items():
        key = f"cycle-test/{file_type}-file"

        await minio_client.put_object(
            bucket=test_bucket,
            key=key,
            data=file_info["content"],
            content_type=file_info["content_type"],
            metadata={"file_type": file_type, "test": "cycle"},
        )

        uploaded_files.append((key, file_info))

    # List all uploaded files
    list_result = await minio_client.list_objects(
        bucket=test_bucket, prefix="cycle-test/"
    )
    assert len(list_result["objects"]) == len(test_files)

    # Download and verify each file
    for key, original_file_info in uploaded_files:
        download_result = await minio_client.get_object(bucket=test_bucket, key=key)

        assert download_result["body"] == original_file_info["content"]
        assert download_result["content_type"] == original_file_info["content_type"]
        assert download_result["metadata"]["test"] == "cycle"

    # Clean up - delete all test files
    for key, _ in uploaded_files:
        await minio_client.delete_object(bucket=test_bucket, key=key)

    # Verify cleanup
    final_list = await minio_client.list_objects(
        bucket=test_bucket, prefix="cycle-test/"
    )
    assert len(final_list["objects"]) == 0


@pytest.mark.asyncio
async def test_metadata_preservation(minio_client, test_bucket, test_files):
    """Test that metadata is properly preserved through upload/download cycle."""
    file_info = test_files["text"]
    key = "metadata-test/complex-metadata.txt"

    # Complex metadata
    metadata = {
        "author": "Test Suite",
        "project": "s3-asyncio-client",
        "version": "1.0.0",
        "description": "E2E test file with complex metadata",
        "tags": "test,e2e,metadata",
        "created": "2025-06-12",
    }

    # Upload with metadata
    await minio_client.put_object(
        bucket=test_bucket,
        key=key,
        data=file_info["content"],
        content_type=file_info["content_type"],
        metadata=metadata,
    )

    # Test head_object metadata
    head_result = await minio_client.head_object(bucket=test_bucket, key=key)
    for key_name, value in metadata.items():
        assert head_result["metadata"][key_name] == value

    # Test get_object metadata
    get_result = await minio_client.get_object(bucket=test_bucket, key=key)
    for key_name, value in metadata.items():
        assert get_result["metadata"][key_name] == value

    # Verify content integrity
    assert get_result["body"] == file_info["content"]


@pytest.mark.asyncio
async def test_error_handling(minio_client, test_bucket):
    """Test error handling for common failure scenarios."""
    from s3_asyncio_client.exceptions import S3NotFoundError

    # Test getting non-existent object
    with pytest.raises(S3NotFoundError):
        await minio_client.get_object(bucket=test_bucket, key="does-not-exist.txt")

    # Test head on non-existent object
    with pytest.raises(S3NotFoundError):
        await minio_client.head_object(bucket=test_bucket, key="does-not-exist.txt")

    # Test delete non-existent object (should succeed - idempotent)
    result = await minio_client.delete_object(
        bucket=test_bucket, key="does-not-exist.txt"
    )
    assert isinstance(result, dict)
