"""Unit tests for list_objects method."""


from s3_asyncio_client import S3Client


async def test_list_objects_basic(monkeypatch):
    """Test basic list_objects functionality."""
    client = S3Client("test-key", "test-secret", "us-east-1")

    # Mock XML response
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
        <Name>test-bucket</Name>
        <Prefix></Prefix>
        <KeyCount>2</KeyCount>
        <MaxKeys>1000</MaxKeys>
        <IsTruncated>false</IsTruncated>
        <Contents>
            <Key>file1.txt</Key>
            <LastModified>2023-10-12T17:50:00.000Z</LastModified>
            <ETag>"abc123"</ETag>
            <Size>100</Size>
            <StorageClass>STANDARD</StorageClass>
        </Contents>
        <Contents>
            <Key>file2.txt</Key>
            <LastModified>2023-10-12T18:00:00.000Z</LastModified>
            <ETag>"def456"</ETag>
            <Size>200</Size>
            <StorageClass>STANDARD</StorageClass>
        </Contents>
    </ListBucketResult>"""

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

    result = await client.list_objects("test-bucket")

    # Check that _make_request was called correctly
    assert len(calls) == 1
    assert calls[0] == {
        "method": "GET",
        "bucket": "test-bucket",
        "params": {"list-type": "2", "max-keys": "1000"},
    }

    # Check result
    assert len(result["objects"]) == 2
    assert result["is_truncated"] is False
    assert result["next_continuation_token"] is None
    assert result["prefix"] is None
    assert result["max_keys"] == 1000

    # Check first object
    obj1 = result["objects"][0]
    assert obj1["key"] == "file1.txt"
    assert obj1["last_modified"] == "2023-10-12T17:50:00.000Z"
    assert obj1["etag"] == "abc123"
    assert obj1["size"] == 100
    assert obj1["storage_class"] == "STANDARD"


async def test_list_objects_with_prefix(monkeypatch):
    """Test list_objects with prefix filter."""
    client = S3Client("test-key", "test-secret", "us-east-1")

    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
        <IsTruncated>false</IsTruncated>
    </ListBucketResult>"""

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

    await client.list_objects("test-bucket", prefix="photos/", max_keys=50)

    # Check that prefix and max_keys were passed correctly
    assert len(calls) == 1
    assert calls[0] == {
        "method": "GET",
        "bucket": "test-bucket",
        "params": {
            "list-type": "2",
            "max-keys": "50",
            "prefix": "photos/",
        },
    }


async def test_list_objects_with_pagination(monkeypatch):
    """Test list_objects with continuation token."""
    client = S3Client("test-key", "test-secret", "us-east-1")

    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
        <IsTruncated>true</IsTruncated>
        <NextContinuationToken>token123</NextContinuationToken>
        <Contents>
            <Key>file1.txt</Key>
            <LastModified>2023-10-12T17:50:00.000Z</LastModified>
            <ETag>"abc123"</ETag>
            <Size>100</Size>
        </Contents>
    </ListBucketResult>"""

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

    result = await client.list_objects("test-bucket", continuation_token="prev-token")

    # Check pagination parameters
    assert len(calls) == 1
    assert calls[0] == {
        "method": "GET",
        "bucket": "test-bucket",
        "params": {
            "list-type": "2",
            "max-keys": "1000",
            "continuation-token": "prev-token",
        },
    }

    # Check pagination result
    assert result["is_truncated"] is True
    assert result["next_continuation_token"] == "token123"


async def test_list_objects_empty(monkeypatch):
    """Test list_objects with empty result."""
    client = S3Client("test-key", "test-secret", "us-east-1")

    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
        <IsTruncated>false</IsTruncated>
    </ListBucketResult>"""

    class MockResponse:
        async def text(self):
            return xml_response

        def close(self):
            pass

    mock_response = MockResponse()

    async def mock_make_request(**kwargs):
        return mock_response

    monkeypatch.setattr(client, "_make_request", mock_make_request)

    result = await client.list_objects("empty-bucket")

    # Check empty result
    assert len(result["objects"]) == 0
    assert result["is_truncated"] is False
    assert result["next_continuation_token"] is None
