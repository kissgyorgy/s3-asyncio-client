# Advanced Usage

This guide covers advanced features and patterns for using the S3 Asyncio Client effectively.

## Multipart Uploads

For large files (>5MB), multipart uploads provide better performance, reliability, and the ability to resume interrupted uploads.

### Automatic Multipart Upload

The simplest way to handle large files is using `upload_file_multipart()`, which automatically manages the multipart process:

```python
async with S3Client(access_key, secret_key, region) as client:
    # Read large file
    with open("/path/to/large-file.bin", "rb") as f:
        large_data = f.read()  # e.g., 100MB file
    
    # Upload with custom part size (default: 5MB)
    result = await client.upload_file_multipart(
        bucket="my-bucket",
        key="large-file.bin",
        data=large_data,
        part_size=10 * 1024 * 1024,  # 10MB parts
        content_type="application/octet-stream",
        metadata={"source": "backup", "compressed": "true"}
    )
    
    print(f"Upload completed: {result['etag']}")
    print(f"Parts uploaded: {result['parts_count']}")
```

### Manual Multipart Upload Control

For fine-grained control, you can manually manage the multipart upload process:

```python
async with S3Client(access_key, secret_key, region) as client:
    # Step 1: Initiate multipart upload
    multipart = await client.create_multipart_upload(
        bucket="my-bucket",
        key="manual-upload.bin",
        content_type="application/octet-stream",
        metadata={"upload_method": "manual"}
    )
    
    try:
        # Step 2: Upload parts
        part_size = 5 * 1024 * 1024  # 5MB
        part_number = 1
        
        with open("/path/to/large-file.bin", "rb") as f:
            while True:
                # Read next chunk
                chunk = f.read(part_size)
                if not chunk:
                    break
                
                # Upload part
                part_info = await multipart.upload_part(part_number, chunk)
                print(f"Uploaded part {part_number}: {part_info['etag']}")
                
                part_number += 1
        
        # Step 3: Complete upload
        result = await multipart.complete()
        print(f"Upload completed: {result['location']}")
        
    except Exception as e:
        # Step 4: Abort on error
        await multipart.abort()
        print(f"Upload aborted due to error: {e}")
        raise
```

### Concurrent Part Uploads

Upload multiple parts concurrently for better performance:

```python
import asyncio

async def upload_part_with_retry(multipart, part_number, data, max_retries=3):
    """Upload a part with retry logic."""
    for attempt in range(max_retries):
        try:
            return await multipart.upload_part(part_number, data)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            print(f"Part {part_number} attempt {attempt + 1} failed: {e}")
            await asyncio.sleep(2 ** attempt)  # Exponential backoff

async def upload_large_file_concurrent(client, bucket, key, file_path, part_size=5*1024*1024, max_concurrency=5):
    """Upload large file with concurrent parts."""
    # Initiate multipart upload
    multipart = await client.create_multipart_upload(bucket, key)
    
    try:
        # Read and split file into parts
        parts_data = []
        with open(file_path, "rb") as f:
            part_number = 1
            while True:
                chunk = f.read(part_size)
                if not chunk:
                    break
                parts_data.append((part_number, chunk))
                part_number += 1
        
        # Upload parts with limited concurrency
        semaphore = asyncio.Semaphore(max_concurrency)
        
        async def upload_part_limited(part_number, data):
            async with semaphore:
                return await upload_part_with_retry(multipart, part_number, data)
        
        # Execute uploads concurrently
        tasks = [upload_part_limited(part_num, data) for part_num, data in parts_data]
        results = await asyncio.gather(*tasks)
        
        # Complete upload
        final_result = await multipart.complete()
        return final_result
        
    except Exception:
        await multipart.abort()
        raise

# Usage
async with S3Client(access_key, secret_key, region) as client:
    result = await upload_large_file_concurrent(
        client, "my-bucket", "huge-file.bin", "/path/to/huge-file.bin"
    )
```

### Resumable Uploads

Track upload progress and resume from where you left off:

```python
import json
import os

class ResumableUpload:
    def __init__(self, client, bucket, key, file_path, state_file="upload_state.json"):
        self.client = client
        self.bucket = bucket
        self.key = key
        self.file_path = file_path
        self.state_file = state_file
        self.multipart = None
        self.completed_parts = {}
    
    def save_state(self):
        """Save upload state to file."""
        state = {
            "bucket": self.bucket,
            "key": self.key,
            "file_path": self.file_path,
            "upload_id": self.multipart.upload_id if self.multipart else None,
            "completed_parts": self.completed_parts
        }
        with open(self.state_file, "w") as f:
            json.dump(state, f)
    
    def load_state(self):
        """Load upload state from file."""
        if os.path.exists(self.state_file):
            with open(self.state_file, "r") as f:
                state = json.load(f)
            self.completed_parts = state.get("completed_parts", {})
            return state.get("upload_id")
        return None
    
    async def upload(self, part_size=5*1024*1024):
        """Upload file with resume capability."""
        # Try to resume existing upload
        upload_id = self.load_state()
        
        if upload_id:
            # Resume existing upload
            from s3_asyncio_client.multipart import MultipartUpload
            self.multipart = MultipartUpload(self.client, self.bucket, self.key, upload_id)
            print(f"Resuming upload with {len(self.completed_parts)} completed parts")
        else:
            # Start new upload
            self.multipart = await self.client.create_multipart_upload(self.bucket, self.key)
            print("Starting new multipart upload")
        
        try:
            file_size = os.path.getsize(self.file_path)
            total_parts = (file_size + part_size - 1) // part_size
            
            with open(self.file_path, "rb") as f:
                for part_number in range(1, total_parts + 1):
                    # Skip already completed parts
                    if str(part_number) in self.completed_parts:
                        f.seek(part_number * part_size)
                        continue
                    
                    # Read part data
                    f.seek((part_number - 1) * part_size)
                    data = f.read(part_size)
                    
                    # Upload part
                    part_info = await self.multipart.upload_part(part_number, data)
                    self.completed_parts[str(part_number)] = part_info
                    
                    # Save progress
                    self.save_state()
                    print(f"Completed part {part_number}/{total_parts}")
            
            # Complete upload
            result = await self.multipart.complete()
            
            # Clean up state file
            if os.path.exists(self.state_file):
                os.remove(self.state_file)
            
            return result
            
        except Exception:
            self.save_state()  # Save current progress
            raise

# Usage
async with S3Client(access_key, secret_key, region) as client:
    uploader = ResumableUpload(client, "my-bucket", "resumable-file.bin", "/path/to/file.bin")
    result = await uploader.upload()
```

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

### Presigned URLs for Multipart Uploads

```python
async def create_presigned_multipart_urls(client, bucket, key, parts_count, expires_in=3600):
    """Create presigned URLs for multipart upload."""
    # Initiate multipart upload
    multipart = await client.create_multipart_upload(bucket, key)
    
    # Generate presigned URLs for each part
    part_urls = {}
    for part_number in range(1, parts_count + 1):
        # Build URL for this part
        url = client._build_url(bucket, key)
        params = {
            "partNumber": str(part_number),
            "uploadId": multipart.upload_id
        }
        
        part_url = client._auth.create_presigned_url(
            method="PUT",
            url=url,
            expires_in=expires_in,
            query_params=params
        )
        part_urls[part_number] = part_url
    
    return {
        "upload_id": multipart.upload_id,
        "part_urls": part_urls,
        "multipart": multipart
    }

# Usage
async with S3Client(access_key, secret_key, region) as client:
    # Create presigned URLs for 5 parts
    result = await create_presigned_multipart_urls(
        client, "my-bucket", "large-file.bin", parts_count=5
    )
    
    # Clients can now upload directly to these URLs
    for part_num, url in result["part_urls"].items():
        print(f"Part {part_num}: {url}")
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

# For very large streams, use multipart upload
async def upload_large_stream(client, bucket, key, stream, part_size=5*1024*1024):
    """Upload large stream using multipart."""
    multipart = await client.create_multipart_upload(bucket, key)
    
    try:
        part_number = 1
        
        while True:
            # Read one part's worth of data
            part_data = await stream.read(part_size)
            if not part_data:
                break
                
            # Upload part
            await multipart.upload_part(part_number, part_data)
            part_number += 1
        
        return await multipart.complete()
        
    except Exception:
        await multipart.abort()
        raise
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

### 2. Use Multipart for Large Files

```python
# Files larger than 5MB should use multipart
file_size = os.path.getsize(file_path)
if file_size > 5 * 1024 * 1024:
    result = await client.upload_file_multipart(bucket, key, data)
else:
    result = await client.put_object(bucket, key, data)
```

### 3. Handle Errors Appropriately

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

### 4. Implement Retry Logic

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