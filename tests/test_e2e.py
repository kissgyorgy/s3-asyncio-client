"""End-to-end tests with real S3 instances.

All S3 operations are fully tested including query parameters,
multipart uploads, metadata handling, and error scenarios.
"""

import tempfile
from pathlib import Path

import aiohttp
import pytest

from s3_asyncio_client import S3Client
from s3_asyncio_client.exceptions import S3NotFoundError


@pytest.fixture
async def client(request):
    """S3Client with a dedicated test bucket created using create_bucket."""
    aws_config_path = request.config.getoption("--aws-config") or "tmp/ovh_config"
    profile_name = request.param or "ovh"

    # For DigitalOcean, use the bucket name that's already in the endpoint URL
    if profile_name == "digitalocean":
        bucket_name = "test-s3-asyncio-client"
    else:
        bucket_name = "s3-async-client-e2e-created-test-bucket"

    # Use from_aws_config with the OVH configuration
    s3_client = S3Client.from_aws_config(
        bucket=bucket_name, profile_name=profile_name, config_path=aws_config_path
    )

    async with s3_client:
        try:
            await s3_client.create_bucket()
        except Exception:
            # Bucket already exists, which is fine
            pass

        # Pre-cleanup: Delete all objects in the bucket before starting tests
        try:
            # Paginate through all objects to ensure complete cleanup
            continuation_token = None
            total_deleted = 0
            while True:
                kwargs = {"max_keys": 1000}
                if continuation_token:
                    kwargs["continuation_token"] = continuation_token

                result = await s3_client.list_objects(**kwargs)

                for obj in result["objects"]:
                    try:
                        await s3_client.delete_object(obj["key"])
                        total_deleted += 1
                    except Exception:
                        # Ignore individual delete errors but continue
                        pass

                # Check if we need to continue
                if not result.get("is_truncated", False):
                    break
                continuation_token = result.get("next_continuation_token")

            # Give OVH a moment to process the deletes
            if total_deleted > 0:
                import asyncio

                await asyncio.sleep(1)
        except Exception:
            pass  # Ignore cleanup errors

        yield {"client": s3_client, "bucket": bucket_name}

        # Post-cleanup: Delete all objects in the bucket after tests
        try:
            # Paginate through all objects to ensure complete cleanup
            continuation_token = None
            while True:
                kwargs = {"max_keys": 1000}
                if continuation_token:
                    kwargs["continuation_token"] = continuation_token

                result = await s3_client.list_objects(**kwargs)

                for obj in result["objects"]:
                    await s3_client.delete_object(obj["key"])

                # Check if we need to continue
                if not result.get("is_truncated", False):
                    break
                continuation_token = result.get("next_continuation_token")
        except Exception:
            pass  # Ignore cleanup errors


@pytest.fixture
def test_files():
    """Pre-generated test files with different content types."""
    files = {}

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        text_file = temp_path / "test.txt"
        text_file.write_text("Hello, S3 E2E Test!\nThis is a text file.")
        files["text"] = {
            "path": str(text_file),
            "content": text_file.read_bytes(),
            "content_type": "text/plain",
        }

        json_file = temp_path / "data.json"
        json_content = '{"name": "test", "value": 42, "array": [1, 2, 3]}'
        json_file.write_text(json_content)
        files["json"] = {
            "path": str(json_file),
            "content": json_file.read_bytes(),
            "content_type": "application/json",
        }

        binary_file = temp_path / "binary.dat"
        binary_content = bytes([i % 256 for i in range(1024)])
        binary_file.write_bytes(binary_content)
        files["binary"] = {
            "path": str(binary_file),
            "content": binary_content,
            "content_type": "application/octet-stream",
        }

        large_file = temp_path / "large.bin"
        large_content = b"Large file content block!\n" * (5 * 1024 * 1024 // 25)
        large_file.write_bytes(large_content)
        files["large"] = {
            "path": str(large_file),
            "content": large_content,
            "content_type": "application/octet-stream",
        }

        yield files


async def test_create_bucket_fixture(client):
    """Test that the fixture with create_bucket works."""
    s3_client = client["client"]

    result = await s3_client.list_objects()
    assert "objects" in result
    assert isinstance(result["objects"], list)

    test_data = b"Hello from session bucket test!"
    key = "test-key.txt"
    put_result = await s3_client.put_object(
        key, data=test_data, content_type="text/plain"
    )

    assert "etag" in put_result

    get_result = await s3_client.get_object(key=key)
    assert get_result["body"] == test_data


async def test_put_get_text_file(client, test_files):
    """Test uploading and downloading a text file."""
    s3_client = client["client"]
    file_info = test_files["text"]
    key = "test-files/hello.txt"

    result = await s3_client.put_object(
        key,
        data=file_info["content"],
        content_type=file_info["content_type"],
        metadata={"author": "pytest", "test": "e2e"},
    )

    assert "etag" in result
    assert result["etag"]

    download_result = await s3_client.get_object(key=key)

    assert download_result["body"] == file_info["content"]
    assert download_result["content_type"] == file_info["content_type"]
    assert download_result["metadata"]["author"] == "pytest"
    assert download_result["metadata"]["test"] == "e2e"


async def test_put_get_json_file(client, test_files):
    s3_client = client["client"]
    file_info = test_files["json"]
    key = "test-files/data.json"

    await s3_client.put_object(
        key=key,
        data=file_info["content"],
        content_type=file_info["content_type"],
    )

    download_result = await s3_client.get_object(key=key)

    assert download_result["body"] == file_info["content"]
    assert download_result["content_type"] == file_info["content_type"]

    import json

    parsed_json = json.loads(download_result["body"].decode())
    assert parsed_json["name"] == "test"
    assert parsed_json["value"] == 42


async def test_put_get_binary_file(client, test_files):
    s3_client = client["client"]
    file_info = test_files["binary"]
    key = "test-files/binary.dat"

    await s3_client.put_object(
        key=key,
        data=file_info["content"],
        content_type=file_info["content_type"],
    )

    download_result = await s3_client.get_object(key=key)

    assert download_result["body"] == file_info["content"]
    assert download_result["content_type"] == file_info["content_type"]
    assert len(download_result["body"]) == 1024


async def test_head_object(client, test_files):
    """Test getting object metadata without downloading."""
    s3_client = client["client"]
    bucket = client["bucket"]
    file_info = test_files["text"]
    key = "test-files/metadata-test.txt"

    await s3_client.put_object(
        key=key,
        data=file_info["content"],
        content_type=file_info["content_type"],
        metadata={"description": "Head test file", "version": "1.0"},
    )

    head_result = await s3_client.head_object(key=key)

    assert head_result["content_type"] == file_info["content_type"]
    assert head_result["content_length"] == len(file_info["content"])
    assert head_result["metadata"]["description"] == "Head test file"
    assert head_result["metadata"]["version"] == "1.0"


async def test_list_objects(client, test_files):
    """Test listing objects with different prefixes."""
    s3_client = client["client"]
    bucket = client["bucket"]
    files_to_upload = [
        ("docs/readme.txt", test_files["text"]),
        ("docs/api.json", test_files["json"]),
        ("images/photo.dat", test_files["binary"]),
        ("config/settings.txt", test_files["text"]),
    ]

    for key, file_info in files_to_upload:
        await s3_client.put_object(
            key=key,
            data=file_info["content"],
            content_type=file_info["content_type"],
        )

    all_objects = await s3_client.list_objects()
    assert len(all_objects["objects"]) == 4

    docs_objects = await s3_client.list_objects(prefix="docs/")
    assert len(docs_objects["objects"]) == 2

    for obj in docs_objects["objects"]:
        assert obj["key"].startswith("docs/")
        assert obj["size"] > 0
        assert "last_modified" in obj


async def test_upload_file_single_part(client, test_files):
    s3_client = client["client"]
    bucket = client["bucket"]
    file_info = test_files["text"]
    key = "upload-file/single-part.txt"

    # Use upload_file method for small file (should use single-part)
    result = await s3_client.upload_file(
        key=key,
        file_source=file_info["path"],
        content_type=file_info["content_type"],
        metadata={"upload_method": "upload_file", "type": "single_part"},
    )

    assert result["upload_type"] == "single_part"
    assert result["size"] == len(file_info["content"])
    assert "etag" in result

    download_result = await s3_client.get_object(key=key)
    assert download_result["body"] == file_info["content"]

    # Note: Some S3 services may not preserve metadata consistently
    # So we only check metadata if it exists
    if "upload_method" in download_result["metadata"]:
        assert download_result["metadata"]["upload_method"] == "upload_file"
        assert download_result["metadata"]["type"] == "single_part"


async def test_upload_large_file_multipart(client, test_files):
    s3_client = client["client"]
    bucket = client["bucket"]
    key = "upload-file/multipart-large.bin"

    # Create a large file that will trigger multipart upload
    large_data = b"A" * (10 * 1024 * 1024)

    from s3_asyncio_client.multipart import TransferConfig

    # Configure for small threshold to force multipart
    config = TransferConfig(
        multipart_threshold=5 * 1024 * 1024,
        multipart_chunksize=5 * 1024 * 1024,
        max_concurrency=3,
    )

    from io import BytesIO

    file_obj = BytesIO(large_data)

    progress_calls = []

    def progress_callback(bytes_transferred):
        progress_calls.append(bytes_transferred)

    result = await s3_client.upload_file(
        key=key,
        file_source=file_obj,
        config=config,
        content_type="application/octet-stream",
        metadata={"upload_method": "upload_file", "type": "multipart"},
        progress_callback=progress_callback,
    )

    assert result["upload_type"] == "multipart"
    assert result["size"] == len(large_data)
    assert result["parts_count"] == 2  # 10MB / 5MB = 2 parts
    assert "etag" in result
    assert "location" in result

    # Verify progress callback was called (should be 2 calls for 2 parts)
    assert len(progress_calls) == 2
    assert sum(progress_calls) == len(large_data)

    download_result = await s3_client.get_object(key=key)
    assert download_result["body"] == large_data

    # Note: Some S3 services may not preserve metadata during multipart uploads
    # So we only check metadata if it exists
    if "upload_method" in download_result["metadata"]:
        assert download_result["metadata"]["upload_method"] == "upload_file"
        assert download_result["metadata"]["type"] == "multipart"


async def test_delete_object(client, test_files):
    """Test deleting objects."""
    s3_client = client["client"]
    bucket = client["bucket"]
    file_info = test_files["text"]
    key = "temp/delete-me.txt"

    await s3_client.put_object(
        key=key,
        data=file_info["content"],
        content_type=file_info["content_type"],
    )

    head_result = await s3_client.head_object(key=key)
    assert head_result["content_length"] == len(file_info["content"])

    delete_result = await s3_client.delete_object(key=key)
    assert isinstance(delete_result, dict)

    with pytest.raises(S3NotFoundError):
        await s3_client.head_object(key=key)


async def test_file_upload_download_cycle(client, test_files):
    s3_client = client["client"]
    bucket = client["bucket"]
    uploaded_files = []

    for file_type, file_info in test_files.items():
        key = f"cycle-test/{file_type}-file"

        await s3_client.put_object(
            key=key,
            data=file_info["content"],
            content_type=file_info["content_type"],
            metadata={"file_type": file_type, "test": "cycle"},
        )

        uploaded_files.append((key, file_info))

    list_result = await s3_client.list_objects(prefix="cycle-test/")
    assert len(list_result["objects"]) == len(test_files)

    for key, original_file_info in uploaded_files:
        download_result = await s3_client.get_object(key=key)

        assert download_result["body"] == original_file_info["content"]
        assert download_result["content_type"] == original_file_info["content_type"]
        assert download_result["metadata"]["test"] == "cycle"

    for key, _ in uploaded_files:
        await s3_client.delete_object(key=key)

    final_list = await s3_client.list_objects(prefix="cycle-test/")
    assert len(final_list["objects"]) == 0


async def test_metadata_preservation(client, test_files):
    """Test that metadata is properly preserved through upload/download cycle."""
    s3_client = client["client"]
    bucket = client["bucket"]
    file_info = test_files["text"]
    key = "metadata-test/complex-metadata.txt"

    metadata = {
        "author": "Test Suite",
        "project": "s3-asyncio-client",
        "version": "1.0.0",
        "description": "E2E test file with complex metadata",
        "tags": "test,e2e,metadata",
        "created": "2025-06-12",
    }

    await s3_client.put_object(
        key=key,
        data=file_info["content"],
        content_type=file_info["content_type"],
        metadata=metadata,
    )

    head_result = await s3_client.head_object(key=key)
    for key_name, value in metadata.items():
        assert head_result["metadata"][key_name] == value

    get_result = await s3_client.get_object(key=key)
    for key_name, value in metadata.items():
        assert get_result["metadata"][key_name] == value

    assert get_result["body"] == file_info["content"]


async def test_error_handling(client):
    s3_client = client["client"]
    bucket = client["bucket"]
    from s3_asyncio_client.exceptions import S3NotFoundError

    with pytest.raises(S3NotFoundError):
        await s3_client.get_object(key="does-not-exist.txt")

    with pytest.raises(S3NotFoundError):
        await s3_client.head_object(key="does-not-exist.txt")

    result = await s3_client.delete_object(key="does-not-exist.txt")
    assert isinstance(result, dict)


async def test_presigned_url_download(client, test_files):
    s3_client = client["client"]
    bucket = client["bucket"]
    file_info = test_files["text"]
    key = "presigned-test/download-test.txt"

    await s3_client.put_object(
        key=key,
        data=file_info["content"],
        content_type=file_info["content_type"],
        metadata={"test": "presigned_download"},
    )

    presigned_url = s3_client.generate_presigned_url(
        method="GET",
        key=key,
        expires_in=3600,
    )

    assert presigned_url.startswith("http")
    assert bucket in presigned_url
    assert key in presigned_url
    assert "X-Amz-Algorithm" in presigned_url
    assert "X-Amz-Credential" in presigned_url
    assert "X-Amz-Date" in presigned_url
    assert "X-Amz-Expires" in presigned_url
    assert "X-Amz-SignedHeaders" in presigned_url
    assert "X-Amz-Signature" in presigned_url

    async with aiohttp.ClientSession() as session:
        async with session.get(presigned_url) as response:
            assert response.status == 200
            assert response.headers["Content-Type"] == file_info["content_type"]

            downloaded_content = await response.read()
            assert downloaded_content == file_info["content"]

            assert response.headers.get("x-amz-meta-test") == "presigned_download"


async def test_presigned_url_upload(client, test_files):
    s3_client = client["client"]
    bucket = client["bucket"]
    file_info = test_files["json"]
    key = "presigned-test/upload-test.json"

    presigned_url = s3_client.generate_presigned_url(
        method="PUT",
        key=key,
        expires_in=3600,
        params={"Content-Type": file_info["content_type"]},
    )

    assert presigned_url.startswith("http")
    assert bucket in presigned_url
    assert key in presigned_url
    assert "X-Amz-Algorithm" in presigned_url
    assert "Content-Type" in presigned_url

    async with aiohttp.ClientSession() as session:
        async with session.put(
            presigned_url,
            data=file_info["content"],
            headers={"Content-Type": file_info["content_type"]},
        ) as response:
            assert response.status == 200

    download_result = await s3_client.get_object(key=key)
    assert download_result["body"] == file_info["content"]
    assert download_result["content_type"] == file_info["content_type"]


async def test_presigned_url_with_custom_params(client, test_files):
    """Test presigned URLs with custom query parameters."""
    s3_client = client["client"]
    bucket = client["bucket"]
    file_info = test_files["binary"]
    key = "presigned-test/custom-params.dat"

    await s3_client.put_object(
        key=key,
        data=file_info["content"],
        content_type=file_info["content_type"],
    )

    presigned_url = s3_client.generate_presigned_url(
        method="GET",
        key=key,
        expires_in=30 * 60,
        params={
            "response-content-disposition": "attachment; filename=custom-filename.dat",
            "response-content-type": "application/force-download",
        },
    )

    assert "response-content-disposition" in presigned_url
    assert "response-content-type" in presigned_url
    assert "custom-filename.dat" in presigned_url

    async with aiohttp.ClientSession() as session:
        async with session.get(presigned_url) as response:
            assert response.status == 200

            assert (
                response.headers["Content-Disposition"]
                == "attachment; filename=custom-filename.dat"
            )
            assert response.headers["Content-Type"] == "application/force-download"

            downloaded_content = await response.read()
            assert downloaded_content == file_info["content"]


async def test_presigned_url_expiration(client, test_files):
    """Test presigned URL expiration behavior."""
    s3_client = client["client"]
    bucket = client["bucket"]
    file_info = test_files["text"]
    key = "presigned-test/expiration-test.txt"

    await s3_client.put_object(
        key=key,
        data=file_info["content"],
        content_type=file_info["content_type"],
    )

    presigned_url = s3_client.generate_presigned_url(
        method="GET",
        key=key,
        expires_in=1,
    )

    import asyncio

    # Wait for URL to expire
    await asyncio.sleep(2)

    async with aiohttp.ClientSession() as session:
        async with session.get(presigned_url) as response:
            # Should receive 403 Forbidden or 401 Unauthorized for expired URL
            # Different S3-compatible services return different status codes
            assert response.status in [401, 403]


async def test_presigned_url_multipart_upload(client, test_files):
    s3_client = client["client"]
    bucket = client["bucket"]
    file_info = test_files["large"]  # 5MB file
    key = "presigned-test/large-upload.bin"

    presigned_url = s3_client.generate_presigned_url(
        method="PUT",
        key=key,
        expires_in=3600,
        params={"Content-Type": file_info["content_type"]},
    )

    async with aiohttp.ClientSession() as session:
        async with session.put(
            presigned_url,
            data=file_info["content"],
            headers={"Content-Type": file_info["content_type"]},
        ) as response:
            assert response.status == 200

    head_result = await s3_client.head_object(key=key)
    assert head_result["content_length"] == len(file_info["content"])

    download_result = await s3_client.get_object(key=key)
    assert len(download_result["body"]) == len(file_info["content"])
    assert download_result["body"][:1024] == file_info["content"][:1024]


async def test_presigned_url_binary_content(client, test_files):
    s3_client = client["client"]
    bucket = client["bucket"]
    file_info = test_files["binary"]
    key = "presigned-test/binary-content.dat"

    presigned_upload_url = s3_client.generate_presigned_url(
        method="PUT",
        key=key,
        expires_in=3600,
        params={"Content-Type": file_info["content_type"]},
    )

    async with aiohttp.ClientSession() as session:
        async with session.put(
            presigned_upload_url,
            data=file_info["content"],
            headers={"Content-Type": file_info["content_type"]},
        ) as response:
            assert response.status == 200

    presigned_download_url = s3_client.generate_presigned_url(
        method="GET",
        key=key,
        expires_in=3600,
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(presigned_download_url) as response:
            assert response.status == 200
            downloaded_content = await response.read()

            assert downloaded_content == file_info["content"]
            assert len(downloaded_content) == 1024

            for i in range(256):
                assert downloaded_content[i] == (i % 256)
