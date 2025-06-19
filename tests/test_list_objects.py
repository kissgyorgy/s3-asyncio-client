import pytest


@pytest.mark.asyncio
async def test_list_objects_basic(mock_client):
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
    </ListBucketResult>
    """
    mock_client.add_response(xml_response)

    result = await mock_client.list_objects()

    assert len(mock_client.requests) == 1
    assert mock_client.requests[0] == {
        "method": "GET",
        "key": None,
        "headers": None,
        "params": {"list-type": "2", "max-keys": "1000"},
        "data": None,
    }

    assert len(result["objects"]) == 2
    assert result["is_truncated"] is False
    assert result["next_continuation_token"] is None
    assert result["prefix"] is None
    assert result["max_keys"] == 1000

    obj1 = result["objects"][0]
    assert obj1["key"] == "file1.txt"
    assert obj1["last_modified"] == "2023-10-12T17:50:00.000Z"
    assert obj1["etag"] == "abc123"
    assert obj1["size"] == 100
    assert obj1["storage_class"] == "STANDARD"


@pytest.mark.asyncio
async def test_list_objects_with_prefix(mock_client):
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
        <IsTruncated>false</IsTruncated>
    </ListBucketResult>"""
    mock_client.add_response(xml_response)

    await mock_client.list_objects(prefix="photos/", max_keys=50)

    assert len(mock_client.requests) == 1
    assert mock_client.requests[0] == {
        "method": "GET",
        "key": None,
        "headers": None,
        "data": None,
        "params": {
            "list-type": "2",
            "max-keys": "50",
            "prefix": "photos/",
        },
    }


@pytest.mark.asyncio
async def test_list_objects_with_pagination(mock_client):
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
    mock_client.add_response(xml_response)

    result = await mock_client.list_objects(continuation_token="prev-token")

    assert len(mock_client.requests) == 1
    assert mock_client.requests[0] == {
        "method": "GET",
        "key": None,
        "headers": None,
        "data": None,
        "params": {
            "list-type": "2",
            "max-keys": "1000",
            "continuation-token": "prev-token",
        },
    }

    assert result["is_truncated"] is True
    assert result["next_continuation_token"] == "token123"


@pytest.mark.asyncio
async def test_list_objects_empty(mock_client):
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
        <IsTruncated>false</IsTruncated>
    </ListBucketResult>"""

    # Add XML response to mock_client
    mock_client.add_response(xml_response)

    result = await mock_client.list_objects()

    assert len(result["objects"]) == 0
    assert result["is_truncated"] is False
    assert result["next_continuation_token"] is None
