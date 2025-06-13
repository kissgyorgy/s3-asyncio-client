"""End-to-end tests with local minio instance.

These tests assume a local minio server is running at http://localhost:9000
with default credentials (minioadmin/minioadmin).

All S3 operations are fully tested including query parameters, multipart uploads,
metadata handling, and error scenarios.
"""

import tempfile
from pathlib import Path

import pytest

from s3_asyncio_client import S3Client


@pytest.fixture
async def minio_client():
    """S3Client with a dedicated test bucket created using create_bucket."""
    client = S3Client(
        access_key="minioadmin",
        secret_key="minioadmin",
        region="us-east-1",
        endpoint_url="http://localhost:9000",
    )

    bucket_name = "e2e-created-test-bucket"

    async with client:
        # Create the bucket using our new method (ignore if already exists)
        try:
            await client.create_bucket(bucket_name)
        except Exception:
            # Bucket already exists, which is fine
            pass

        # Yield client and bucket info
        yield {"client": client, "bucket": bucket_name}

        # Cleanup: Delete all objects in the bucket
        try:
            result = await client.list_objects(bucket_name, max_keys=1000)
            for obj in result["objects"]:
                await client.delete_object(bucket_name, obj["key"])
        except Exception:
            pass  # Ignore cleanup errors


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


async def test_create_bucket_fixture(minio_client):
    """Test that the fixture with create_bucket works."""
    client = minio_client["client"]
    bucket = minio_client["bucket"]

    # Test that we can list objects in the created bucket
    result = await client.list_objects(bucket)
    assert "objects" in result
    assert isinstance(result["objects"], list)

    # Test that we can put an object in the created bucket
    test_data = b"Hello from session bucket test!"
    key = "test-key.txt"

    put_result = await client.put_object(
        bucket=bucket,
        key=key,
        data=test_data,
        content_type="text/plain",
    )

    assert "etag" in put_result

    # Test that we can get the object back
    get_result = await client.get_object(bucket=bucket, key=key)
    assert get_result["body"] == test_data


async def test_put_get_text_file(minio_client, test_files):
    """Test uploading and downloading a text file."""
    client = minio_client["client"]
    bucket = minio_client["bucket"]
    file_info = test_files["text"]
    key = "test-files/hello.txt"

    # Upload file
    result = await client.put_object(
        bucket=bucket,
        key=key,
        data=file_info["content"],
        content_type=file_info["content_type"],
        metadata={"author": "pytest", "test": "e2e"},
    )

    assert "etag" in result
    assert result["etag"]  # ETag should not be empty

    # Download file
    download_result = await client.get_object(bucket=bucket, key=key)

    assert download_result["body"] == file_info["content"]
    assert download_result["content_type"] == file_info["content_type"]
    assert download_result["metadata"]["author"] == "pytest"
    assert download_result["metadata"]["test"] == "e2e"


async def test_put_get_json_file(minio_client, test_files):
    """Test uploading and downloading a JSON file."""
    client = minio_client["client"]
    bucket = minio_client["bucket"]
    file_info = test_files["json"]
    key = "test-files/data.json"

    # Upload file
    await client.put_object(
        bucket=bucket,
        key=key,
        data=file_info["content"],
        content_type=file_info["content_type"],
    )

    # Download file
    download_result = await client.get_object(bucket=bucket, key=key)

    assert download_result["body"] == file_info["content"]
    assert download_result["content_type"] == file_info["content_type"]

    # Verify JSON content
    import json

    parsed_json = json.loads(download_result["body"].decode())
    assert parsed_json["name"] == "test"
    assert parsed_json["value"] == 42


async def test_put_get_binary_file(minio_client, test_files):
    """Test uploading and downloading a binary file."""
    client = minio_client["client"]
    bucket = minio_client["bucket"]
    file_info = test_files["binary"]
    key = "test-files/binary.dat"

    # Upload file
    await client.put_object(
        bucket=bucket,
        key=key,
        data=file_info["content"],
        content_type=file_info["content_type"],
    )

    # Download file
    download_result = await client.get_object(bucket=bucket, key=key)

    assert download_result["body"] == file_info["content"]
    assert download_result["content_type"] == file_info["content_type"]
    assert len(download_result["body"]) == 1024


async def test_head_object(minio_client, test_files):
    """Test getting object metadata without downloading."""
    client = minio_client["client"]
    bucket = minio_client["bucket"]
    file_info = test_files["text"]
    key = "test-files/metadata-test.txt"

    # Upload file with metadata
    await client.put_object(
        bucket=bucket,
        key=key,
        data=file_info["content"],
        content_type=file_info["content_type"],
        metadata={"description": "Head test file", "version": "1.0"},
    )

    # Get metadata
    head_result = await client.head_object(bucket=bucket, key=key)

    assert head_result["content_type"] == file_info["content_type"]
    assert head_result["content_length"] == len(file_info["content"])
    assert head_result["metadata"]["description"] == "Head test file"
    assert head_result["metadata"]["version"] == "1.0"


async def test_list_objects(minio_client, test_files):
    """Test listing objects with different prefixes."""
    client = minio_client["client"]
    bucket = minio_client["bucket"]
    # Upload multiple files
    files_to_upload = [
        ("docs/readme.txt", test_files["text"]),
        ("docs/api.json", test_files["json"]),
        ("images/photo.dat", test_files["binary"]),
        ("config/settings.txt", test_files["text"]),
    ]

    for key, file_info in files_to_upload:
        await client.put_object(
            bucket=bucket,
            key=key,
            data=file_info["content"],
            content_type=file_info["content_type"],
        )

    # List all objects
    all_objects = await client.list_objects(bucket=bucket)
    assert len(all_objects["objects"]) == 4

    # List with prefix
    docs_objects = await client.list_objects(bucket=bucket, prefix="docs/")
    assert len(docs_objects["objects"]) == 2

    # Verify object details
    for obj in docs_objects["objects"]:
        assert obj["key"].startswith("docs/")
        assert obj["size"] > 0
        assert "last_modified" in obj


async def test_multipart_upload(minio_client, test_files):
    """Test multipart upload with a large file."""
    client = minio_client["client"]
    bucket = minio_client["bucket"]
    file_info = test_files["large"]
    key = "large-files/big-file.bin"

    # Create multipart upload
    multipart = await client.create_multipart_upload(
        bucket=bucket,
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
    download_result = await client.get_object(bucket=bucket, key=key)
    assert download_result["body"] == file_info["content"]
    assert download_result["metadata"]["size"] == "large"
    assert download_result["metadata"]["test"] == "multipart"


async def test_delete_object(minio_client, test_files):
    """Test deleting objects."""
    client = minio_client["client"]
    bucket = minio_client["bucket"]
    file_info = test_files["text"]
    key = "temp/delete-me.txt"

    # Upload file
    await client.put_object(
        bucket=bucket,
        key=key,
        data=file_info["content"],
        content_type=file_info["content_type"],
    )

    # Verify file exists
    head_result = await client.head_object(bucket=bucket, key=key)
    assert head_result["content_length"] == len(file_info["content"])

    # Delete file
    delete_result = await client.delete_object(bucket=bucket, key=key)
    assert isinstance(delete_result, dict)

    # Verify file is gone
    with pytest.raises(Exception):  # Should raise S3NotFoundError
        await client.head_object(bucket=bucket, key=key)


async def test_file_upload_download_cycle(minio_client, test_files):
    """Test complete upload/download cycle for all file types."""
    client = minio_client["client"]
    bucket = minio_client["bucket"]
    uploaded_files = []

    # Upload all test files
    for file_type, file_info in test_files.items():
        key = f"cycle-test/{file_type}-file"

        await client.put_object(
            bucket=bucket,
            key=key,
            data=file_info["content"],
            content_type=file_info["content_type"],
            metadata={"file_type": file_type, "test": "cycle"},
        )

        uploaded_files.append((key, file_info))

    # List all uploaded files
    list_result = await client.list_objects(bucket=bucket, prefix="cycle-test/")
    assert len(list_result["objects"]) == len(test_files)

    # Download and verify each file
    for key, original_file_info in uploaded_files:
        download_result = await client.get_object(bucket=bucket, key=key)

        assert download_result["body"] == original_file_info["content"]
        assert download_result["content_type"] == original_file_info["content_type"]
        assert download_result["metadata"]["test"] == "cycle"

    # Clean up - delete all test files
    for key, _ in uploaded_files:
        await client.delete_object(bucket=bucket, key=key)

    # Verify cleanup
    final_list = await client.list_objects(bucket=bucket, prefix="cycle-test/")
    assert len(final_list["objects"]) == 0


async def test_metadata_preservation(minio_client, test_files):
    """Test that metadata is properly preserved through upload/download cycle."""
    client = minio_client["client"]
    bucket = minio_client["bucket"]
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
    await client.put_object(
        bucket=bucket,
        key=key,
        data=file_info["content"],
        content_type=file_info["content_type"],
        metadata=metadata,
    )

    # Test head_object metadata
    head_result = await client.head_object(bucket=bucket, key=key)
    for key_name, value in metadata.items():
        assert head_result["metadata"][key_name] == value

    # Test get_object metadata
    get_result = await client.get_object(bucket=bucket, key=key)
    for key_name, value in metadata.items():
        assert get_result["metadata"][key_name] == value

    # Verify content integrity
    assert get_result["body"] == file_info["content"]


async def test_error_handling(minio_client):
    """Test error handling for common failure scenarios."""
    client = minio_client["client"]
    bucket = minio_client["bucket"]
    from s3_asyncio_client.exceptions import S3NotFoundError

    # Test getting non-existent object
    with pytest.raises(S3NotFoundError):
        await client.get_object(bucket=bucket, key="does-not-exist.txt")

    # Test head on non-existent object
    with pytest.raises(S3NotFoundError):
        await client.head_object(bucket=bucket, key="does-not-exist.txt")

    # Test delete non-existent object (should succeed - idempotent)
    result = await client.delete_object(bucket=bucket, key="does-not-exist.txt")
    assert isinstance(result, dict)
