# Basic Operations

This guide covers all the basic S3 operations available in the S3 Asyncio Client.

## Overview

The S3Client provides five core operations:

- **put_object**: Upload data to S3
- **get_object**: Download data from S3
- **head_object**: Get object metadata without downloading
- **list_objects**: List objects in a bucket
- **generate_presigned_url**: Create time-limited access URLs

## Put Object

Upload data to S3 with various options.

### Basic Upload

```python
async with S3Client(access_key, secret_key, region) as client:
    # Upload bytes
    await client.put_object("my-bucket", "hello.txt", b"Hello, World!")
    
    # Upload string (converted to bytes)
    content = "Hello, World!"
    await client.put_object("my-bucket", "hello.txt", content.encode())
```

### Upload with Metadata

```python
await client.put_object(
    bucket="my-bucket",
    key="document.pdf",
    data=pdf_content,
    content_type="application/pdf",
    metadata={
        "author": "John Doe",
        "version": "1.0",
        "description": "Important document"
    }
)
```

### Upload File from Disk

```python
async with S3Client(access_key, secret_key, region) as client:
    # Read and upload file
    with open("/path/to/file.txt", "rb") as f:
        content = f.read()
    
    await client.put_object("my-bucket", "uploaded-file.txt", content)
```

### Response Format

```python
response = await client.put_object("my-bucket", "test.txt", b"content")
# Response contains:
# {
#     "etag": "\"d85b1213473c2fd7c2045020a6b9c62b\"",
#     "version_id": "null"  # or actual version if versioning enabled
# }
```

## Get Object

Download data from S3.

### Basic Download

```python
async with S3Client(access_key, secret_key, region) as client:
    response = await client.get_object("my-bucket", "hello.txt")
    
    content = response["body"]  # bytes
    text = content.decode()     # convert to string
    print(text)  # Hello, World!
```

### Access Response Metadata

```python
response = await client.get_object("my-bucket", "document.pdf")

# File content
content = response["body"]

# Metadata
etag = response["etag"]
content_type = response.get("content_type")
content_length = response.get("content_length")
last_modified = response.get("last_modified")
metadata = response.get("metadata", {})

print(f"Downloaded {content_length} bytes")
print(f"Author: {metadata.get('author', 'Unknown')}")
```

### Save to File

```python
async with S3Client(access_key, secret_key, region) as client:
    response = await client.get_object("my-bucket", "large-file.zip")
    
    with open("/path/to/download/large-file.zip", "wb") as f:
        f.write(response["body"])
```

### Response Format

```python
response = await client.get_object("my-bucket", "test.txt")
# Response contains:
# {
#     "body": b"file content",
#     "etag": "\"d85b1213473c2fd7c2045020a6b9c62b\"",
#     "content_type": "text/plain",
#     "content_length": 12,
#     "last_modified": "2023-12-01T10:30:00Z",
#     "metadata": {"key": "value"}
# }
```

## Head Object

Get object metadata without downloading the content.

### Basic Head Request

```python
async with S3Client(access_key, secret_key, region) as client:
    try:
        response = await client.head_object("my-bucket", "hello.txt")
        print(f"File exists! Size: {response['content_length']} bytes")
    except S3NotFoundError:
        print("File does not exist")
```

### Check File Properties

```python
response = await client.head_object("my-bucket", "document.pdf")

# File properties
size = response["content_length"]
content_type = response["content_type"]
last_modified = response["last_modified"]
etag = response["etag"]
metadata = response.get("metadata", {})

print(f"File: {size} bytes, {content_type}")
print(f"Modified: {last_modified}")
print(f"Author: {metadata.get('author', 'Unknown')}")
```

### Response Format

```python
response = await client.head_object("my-bucket", "test.txt")
# Response contains:
# {
#     "etag": "\"d85b1213473c2fd7c2045020a6b9c62b\"",
#     "content_type": "text/plain",
#     "content_length": 12,
#     "last_modified": "2023-12-01T10:30:00Z",
#     "metadata": {"key": "value"}
# }
```

## List Objects

List objects in a bucket with optional filtering.

### Basic Listing

```python
async with S3Client(access_key, secret_key, region) as client:
    response = await client.list_objects("my-bucket")
    
    for obj in response.get("contents", []):
        print(f"Key: {obj['key']}")
        print(f"Size: {obj['size']} bytes")
        print(f"Modified: {obj['last_modified']}")
        print(f"ETag: {obj['etag']}")
        print("---")
```

### List with Prefix Filter

```python
# List only objects starting with "documents/"
response = await client.list_objects("my-bucket", prefix="documents/")

for obj in response.get("contents", []):
    print(f"Document: {obj['key']}")
```

### Paginated Listing

```python
async with S3Client(access_key, secret_key, region) as client:
    continuation_token = None
    
    while True:
        response = await client.list_objects(
            bucket="my-bucket",
            max_keys=100,  # Process 100 objects at a time
            continuation_token=continuation_token
        )
        
        # Process objects
        for obj in response.get("contents", []):
            print(f"Processing: {obj['key']}")
        
        # Check if there are more objects
        if not response.get("is_truncated", False):
            break
            
        continuation_token = response.get("next_continuation_token")
```

### Response Format

```python
response = await client.list_objects("my-bucket")
# Response contains:
# {
#     "is_truncated": False,
#     "contents": [
#         {
#             "key": "file1.txt",
#             "last_modified": "2023-12-01T10:30:00Z",
#             "etag": "\"abc123\"",
#             "size": 1024,
#             "storage_class": "STANDARD"
#         }
#     ],
#     "name": "my-bucket",
#     "prefix": "",
#     "max_keys": 1000,
#     "common_prefixes": []
# }
```

## Generate Presigned URL

Create time-limited URLs for secure access to S3 objects.

### Basic Presigned URL

```python
# Generate URL valid for 1 hour (3600 seconds)
url = client.generate_presigned_url(
    method="GET",
    bucket="my-bucket",
    key="hello.txt",
    expires_in=3600
)

print(f"Download URL: {url}")
# Users can access this URL directly in their browser
```

### Upload Presigned URL

```python
# Generate URL for uploading
upload_url = client.generate_presigned_url(
    method="PUT",
    bucket="my-bucket",
    key="upload-target.txt",
    expires_in=1800  # 30 minutes
)

# Users can PUT to this URL to upload files
print(f"Upload URL: {upload_url}")
```

### Presigned URL with Parameters

```python
# Add custom parameters
url = client.generate_presigned_url(
    method="GET",
    bucket="my-bucket",
    key="document.pdf",
    expires_in=3600,
    params={
        "response-content-disposition": "attachment; filename=document.pdf",
        "response-content-type": "application/pdf"
    }
)
```

### Using Presigned URLs

```python
import aiohttp

# Download using presigned URL
async with aiohttp.ClientSession() as session:
    async with session.get(presigned_url) as response:
        content = await response.read()

# Upload using presigned URL
async with aiohttp.ClientSession() as session:
    async with session.put(upload_url, data=file_content) as response:
        if response.status == 200:
            print("Upload successful!")
```

## Error Handling

All operations can raise specific S3 exceptions:

```python
from s3_asyncio_client import (
    S3NotFoundError,
    S3AccessDeniedError,
    S3InvalidRequestError,
    S3ClientError,
    S3ServerError
)

async with S3Client(access_key, secret_key, region) as client:
    try:
        response = await client.get_object("my-bucket", "nonexistent.txt")
    except S3NotFoundError:
        print("Object not found")
    except S3AccessDeniedError:
        print("Access denied - check permissions")
    except S3ClientError as e:
        print(f"Client error: {e.message} (status: {e.status_code})")
    except S3ServerError as e:
        print(f"Server error: {e.message} (status: {e.status_code})")
```

## Performance Tips

### Concurrent Operations

```python
import asyncio

async with S3Client(access_key, secret_key, region) as client:
    # Upload multiple files concurrently
    tasks = []
    
    for i in range(10):
        task = client.put_object(
            "my-bucket", 
            f"file-{i}.txt", 
            f"Content {i}".encode()
        )
        tasks.append(task)
    
    # Wait for all uploads to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"File {i} failed: {result}")
        else:
            print(f"File {i} uploaded successfully")
```

### Reuse Client Sessions

```python
# Good: Reuse client for multiple operations
async with S3Client(access_key, secret_key, region) as client:
    await client.put_object("bucket", "file1.txt", b"content1")
    await client.put_object("bucket", "file2.txt", b"content2")
    await client.get_object("bucket", "file1.txt")

# Avoid: Creating new client for each operation
# This creates unnecessary HTTP session overhead
```

## Next Steps

- Learn about [Advanced Usage](advanced-usage.md) for multipart uploads
- Check [Error Handling](error-handling.md) for comprehensive error management
- See [Performance Tips](performance.md) for optimization strategies
- Browse [Examples](../examples/basic.md) for real-world use cases