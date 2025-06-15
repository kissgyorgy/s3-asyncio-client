# Advanced Usage

This guide covers advanced features and patterns for using the S3 Asyncio Client effectively.

## Advanced S3 Operations

### Custom Headers and Parameters

Add custom headers and query parameters to requests:

```python
# Custom headers for put_object (modify client._make_request)
async def put_object_with_custom_headers(client, bucket, key, data, custom_headers=None):
    """Upload object with custom headers."""
    headers = {
        "Content-Length": str(len(data)),
        "Content-Type": "application/octet-stream"
    }
    
    # Add custom headers
    if custom_headers:
        headers.update(custom_headers)
    
    # Use client's internal method with custom headers
    response = await client._make_request(
        method="PUT",
        bucket=bucket,
        key=key,
        headers=headers,
        data=data
    )
    
    return {
        "etag": response.headers.get("ETag", "").strip('"'),
        "version_id": response.headers.get("x-amz-version-id"),
    }

# Usage
async with S3Client(access_key, secret_key, region) as client:
    result = await put_object_with_custom_headers(
        client, "my-bucket", "custom-file.txt", b"content",
        custom_headers={
            "Cache-Control": "max-age=3600",
            "x-amz-storage-class": "REDUCED_REDUNDANCY",
            "x-amz-server-side-encryption": "AES256"
        }
    )
```

### Server-Side Encryption

Upload objects with server-side encryption:

```python
async def put_object_encrypted(client, bucket, key, data, encryption_method="AES256", kms_key_id=None):
    """Upload object with server-side encryption."""
    headers = {
        "Content-Length": str(len(data)),
        "Content-Type": "application/octet-stream"
    }
    
    if encryption_method == "AES256":
        headers["x-amz-server-side-encryption"] = "AES256"
    elif encryption_method == "KMS":
        headers["x-amz-server-side-encryption"] = "aws:kms"
        if kms_key_id:
            headers["x-amz-server-side-encryption-aws-kms-key-id"] = kms_key_id
    
    response = await client._make_request(
        method="PUT",
        bucket=bucket,
        key=key,
        headers=headers,
        data=data
    )
    
    return {
        "etag": response.headers.get("ETag", "").strip('"'),
        "encryption": response.headers.get("x-amz-server-side-encryption"),
        "kms_key_id": response.headers.get("x-amz-server-side-encryption-aws-kms-key-id"),
    }

# Usage
async with S3Client(access_key, secret_key, region) as client:
    # AES256 encryption
    result = await put_object_encrypted(
        client, "my-bucket", "encrypted-file.txt", 
        b"sensitive data", encryption_method="AES256"
    )
    
    # KMS encryption
    result = await put_object_encrypted(
        client, "my-bucket", "kms-encrypted.txt", 
        b"very sensitive data", 
        encryption_method="KMS",
        kms_key_id="arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"
    )
```

### Object Versioning Support

Work with versioned objects:

```python
async def get_object_version(client, bucket, key, version_id):
    """Get specific version of an object."""
    params = {"versionId": version_id}
    
    response = await client._make_request(
        method="GET",
        bucket=bucket,
        key=key,
        params=params
    )
    
    body = await response.read()
    
    return {
        "body": body,
        "version_id": response.headers.get("x-amz-version-id"),
        "etag": response.headers.get("ETag", "").strip('"'),
        "last_modified": response.headers.get("Last-Modified"),
    }

async def list_object_versions(client, bucket, prefix=None, max_keys=1000):
    """List all versions of objects in a bucket."""
    params = {"versions": "", "max-keys": str(max_keys)}
    if prefix:
        params["prefix"] = prefix
    
    response = await client._make_request(
        method="GET",
        bucket=bucket,
        params=params
    )
    
    response_text = await response.text()
    # Parse XML response to extract versions
    # Implementation would parse the ListVersionsResult XML
    return response_text

# Usage
async with S3Client(access_key, secret_key, region) as client:
    # Get specific version
    version_data = await get_object_version(
        client, "versioned-bucket", "file.txt", "version-id-123"
    )
    
    # List all versions
    versions = await list_object_versions(client, "versioned-bucket", prefix="documents/")
```

### Object Tagging

Add and manage object tags:

```python
async def put_object_with_tags(client, bucket, key, data, tags=None):
    """Upload object with tags."""
    headers = {"Content-Length": str(len(data))}
    
    if tags:
        # URL encode tags for the header
        import urllib.parse
        tag_pairs = [f"{k}={urllib.parse.quote(str(v))}" for k, v in tags.items()]
        headers["x-amz-tagging"] = "&".join(tag_pairs)
    
    response = await client._make_request(
        method="PUT",
        bucket=bucket,
        key=key,
        headers=headers,
        data=data
    )
    
    return {
        "etag": response.headers.get("ETag", "").strip('"'),
        "version_id": response.headers.get("x-amz-version-id"),
    }

async def get_object_tags(client, bucket, key):
    """Get object tags."""
    params = {"tagging": ""}
    
    response = await client._make_request(
        method="GET",
        bucket=bucket,
        key=key,
        params=params
    )
    
    # Parse XML response to extract tags
    response_text = await response.text()
    # Implementation would parse TagSet XML
    return response_text

# Usage
async with S3Client(access_key, secret_key, region) as client:
    # Upload with tags
    result = await put_object_with_tags(
        client, "my-bucket", "tagged-file.txt", b"content",
        tags={"Environment": "Production", "Team": "Engineering", "Cost-Center": "123"}
    )
    
    # Get tags
    tags = await get_object_tags(client, "my-bucket", "tagged-file.txt")
```

## Working with S3-Compatible Services

The client works with any S3-compatible service by specifying a custom endpoint:

### MinIO

```python
# Connect to MinIO server
async with S3Client(
    access_key="minioadmin",
    secret_key="minioadmin",
    region="us-east-1",
    endpoint_url="http://localhost:9000"
) as client:
    await client.put_object("test-bucket", "test.txt", b"Hello MinIO!")
```

### DigitalOcean Spaces

```python
# Connect to DigitalOcean Spaces
async with S3Client(
    access_key="your-spaces-key",
    secret_key="your-spaces-secret",
    region="nyc3",
    endpoint_url="https://nyc3.digitaloceanspaces.com"
) as client:
    await client.put_object("my-space", "file.txt", b"Hello Spaces!")
```

### Wasabi

```python
# Connect to Wasabi
async with S3Client(
    access_key="your-wasabi-key",
    secret_key="your-wasabi-secret",
    region="us-east-1",
    endpoint_url="https://s3.wasabisys.com"
) as client:
    await client.put_object("my-bucket", "file.txt", b"Hello Wasabi!")
```

## Advanced Presigned URLs

### Presigned URLs with Custom Headers

```python
def generate_presigned_upload_url(client, bucket, key, expires_in=3600, content_type=None):
    """Generate presigned URL for upload with specific content type."""
    params = {}
    if content_type:
        params["Content-Type"] = content_type
    
    return client.generate_presigned_url(
        method="PUT",
        bucket=bucket,
        key=key,
        expires_in=expires_in,
        params=params
    )

# Usage
client = S3Client(access_key, secret_key, region)

# Generate URL that requires specific content type
upload_url = generate_presigned_upload_url(
    client, "my-bucket", "document.pdf", 
    content_type="application/pdf"
)

# Client must include Content-Type header when uploading
```


## Connection Management

### Connection Pooling

The client automatically manages connection pooling through aiohttp:

```python
import aiohttp

# Custom session with connection pooling
connector = aiohttp.TCPConnector(
    limit=100,  # Total connection pool size
    limit_per_host=10,  # Max connections per host
    ttl_dns_cache=300,  # DNS cache TTL
    use_dns_cache=True,
)

async with aiohttp.ClientSession(connector=connector) as session:
    # Override the client's session
    client = S3Client(access_key, secret_key, region)
    client._session = session
    
    # Perform operations with custom connection pooling
    tasks = [
        client.put_object("bucket", f"file-{i}.txt", f"content-{i}".encode())
        for i in range(100)
    ]
    
    results = await asyncio.gather(*tasks)
```

### Timeout Configuration

```python
import aiohttp

# Custom timeout settings
timeout = aiohttp.ClientTimeout(
    total=300,  # Total timeout for request
    connect=30,  # Connection timeout
    sock_read=60,  # Socket read timeout
)

async with aiohttp.ClientSession(timeout=timeout) as session:
    client = S3Client(access_key, secret_key, region)
    client._session = session
    
    # Operations will use custom timeouts
    await client.put_object("bucket", "file.txt", b"content")
```

## Streaming and Memory Efficiency

### Streaming Large Downloads

```python
async def stream_large_object(client, bucket, key, chunk_size=8192):
    """Stream large object without loading entire file into memory."""
    response = await client._make_request(
        method="GET",
        bucket=bucket,
        key=key
    )
    
    # Stream the response
    chunks = []
    async for chunk in response.content.iter_chunked(chunk_size):
        chunks.append(chunk)
        # Process chunk immediately to avoid memory buildup
        yield chunk
    
    return b''.join(chunks)

# Usage
async with S3Client(access_key, secret_key, region) as client:
    async for chunk in stream_large_object(client, "bucket", "huge-file.bin"):
        # Process each chunk as it arrives
        print(f"Received chunk of {len(chunk)} bytes")
```

### Memory-Efficient Uploads

```python
async def upload_from_stream(client, bucket, key, stream, chunk_size=8192):
    """Upload from a stream without loading everything into memory."""
    chunks = []
    
    # Read stream in chunks
    while True:
        chunk = await stream.read(chunk_size)
        if not chunk:
            break
        chunks.append(chunk)
    
    # Combine chunks and upload
    data = b''.join(chunks)
    return await client.put_object(bucket, key, data)

```

## Best Practices

### 1. Always Use Async Context Managers

```python
# Good: Ensures proper cleanup
async with S3Client(access_key, secret_key, region) as client:
    await client.put_object("bucket", "file.txt", b"content")

# Avoid: Manual session management
client = S3Client(access_key, secret_key, region)
try:
    await client.put_object("bucket", "file.txt", b"content")
finally:
    await client.close()
```

### 2. Handle Errors Appropriately

```python
from s3_asyncio_client.exceptions import S3Error, S3NotFoundError

try:
    result = await client.get_object("bucket", "file.txt")
except S3NotFoundError:
    # Handle missing file specifically
    print("File not found")
except S3Error as e:
    # Handle other S3 errors
    print(f"S3 error: {e}")
except Exception as e:
    # Handle network and other errors
    print(f"Unexpected error: {e}")
```

### 3. Implement Retry Logic

```python
import asyncio
import random

async def retry_operation(operation, max_retries=3, base_delay=1):
    """Retry operation with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return await operation()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            await asyncio.sleep(delay)

# Usage
async def upload_with_retry():
    return await client.put_object("bucket", "file.txt", b"content")

result = await retry_operation(upload_with_retry)
```

## Next Steps

- Review [Error Handling](error-handling.md) for comprehensive error management
- Check [Performance Tips](performance.md) for optimization strategies
- Browse [Examples](../examples/) for complete working examples
- See [API Reference](../reference/) for detailed method documentation