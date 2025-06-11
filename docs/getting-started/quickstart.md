# Quick Start

This guide will help you get up and running with S3 Asyncio Client in just a few minutes.

## Basic Setup

First, create an S3Client instance with your credentials:

```python
import asyncio
from s3_asyncio_client import S3Client

async def main():
    # Create client with AWS credentials
    client = S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key",
        region="us-east-1"  # Your preferred region
    )
    
    # Always close the client when done
    await client.close()

asyncio.run(main())
```

## Using Context Manager (Recommended)

The recommended way to use the client is with an async context manager:

```python
import asyncio
from s3_asyncio_client import S3Client

async def main():
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key",
        region="us-east-1"
    ) as client:
        # Client will be automatically closed when exiting this block
        pass

asyncio.run(main())
```

## Basic Operations

### Upload a File

```python
async with S3Client(access_key, secret_key, region) as client:
    # Upload bytes
    await client.put_object("my-bucket", "hello.txt", b"Hello, World!")
    
    # Upload with metadata
    await client.put_object(
        bucket="my-bucket",
        key="document.pdf",
        data=file_content,
        content_type="application/pdf",
        metadata={"author": "John Doe", "version": "1.0"}
    )
```

### Download a File

```python
async with S3Client(access_key, secret_key, region) as client:
    response = await client.get_object("my-bucket", "hello.txt")
    
    content = response["body"]  # bytes
    etag = response["etag"]
    content_type = response.get("content_type")
    metadata = response.get("metadata", {})
    
    print(content.decode())  # Hello, World!
```

### Check if File Exists

```python
async with S3Client(access_key, secret_key, region) as client:
    try:
        response = await client.head_object("my-bucket", "hello.txt")
        print(f"File exists! Size: {response['content_length']} bytes")
    except S3NotFoundError:
        print("File does not exist")
```

### List Files in Bucket

```python
async with S3Client(access_key, secret_key, region) as client:
    response = await client.list_objects("my-bucket", prefix="documents/")
    
    for obj in response.get("contents", []):
        print(f"Key: {obj['key']}, Size: {obj['size']}")
```

### Generate Pre-signed URL

```python
async with S3Client(access_key, secret_key, region) as client:
    # Generate URL valid for 1 hour
    url = client.generate_presigned_url(
        method="GET",
        bucket="my-bucket",
        key="hello.txt",
        expires_in=3600
    )
    print(f"Download URL: {url}")
```

## Complete Example

Here's a complete example that demonstrates all basic operations:

```python
import asyncio
from s3_asyncio_client import S3Client, S3NotFoundError

async def demo():
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key",
        region="us-east-1"
    ) as client:
        bucket = "my-test-bucket"
        key = "demo-file.txt"
        content = b"This is a demo file content!"
        
        # Upload file
        print("Uploading file...")
        await client.put_object(bucket, key, content)
        
        # Check if file exists
        print("Checking if file exists...")
        try:
            info = await client.head_object(bucket, key)
            print(f"File exists! Size: {info['content_length']} bytes")
        except S3NotFoundError:
            print("File not found!")
            return
        
        # Download file
        print("Downloading file...")
        response = await client.get_object(bucket, key)
        downloaded_content = response["body"]
        print(f"Downloaded: {downloaded_content.decode()}")
        
        # List files
        print("Listing files...")
        response = await client.list_objects(bucket)
        for obj in response.get("contents", []):
            print(f"Found: {obj['key']} ({obj['size']} bytes)")
        
        # Generate pre-signed URL
        print("Generating pre-signed URL...")
        url = client.generate_presigned_url("GET", bucket, key, expires_in=3600)
        print(f"Pre-signed URL: {url}")

if __name__ == "__main__":
    asyncio.run(demo())
```

## Next Steps

- Learn about [Configuration](configuration.md) options
- Explore [Basic Operations](../guide/basic-operations.md) in detail
- Check out [Advanced Usage](../guide/advanced-usage.md) for multipart uploads and more
- Browse [Examples](../examples/basic.md) for common use cases