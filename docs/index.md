# S3 Asyncio Client

A minimal, fast, and simple asyncio-based Amazon S3 client library for Python.

## Features

- **Async/Await Support**: Built from the ground up with asyncio for non-blocking I/O operations
- **Minimal Dependencies**: Only requires `aiohttp` for HTTP operations
- **S3 Compatible**: Works with Amazon S3 and S3-compatible services (MinIO, DigitalOcean Spaces, etc.)
- **Full Authentication**: Complete AWS Signature Version 4 implementation
- **Pre-signed URLs**: Generate time-limited URLs for secure access
- **Comprehensive Error Handling**: Detailed exception hierarchy for different S3 errors

## Core Operations

- **put_object**: Upload files and data to S3
- **get_object**: Download files and data from S3
- **head_object**: Get object metadata without downloading content
- **list_objects**: List objects in a bucket with optional filtering
- **generate_presigned_url**: Create secure, time-limited URLs

## Quick Example

```python
import asyncio
from s3_asyncio_client import S3Client

async def main():
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key",
        region="us-east-1"
    ) as client:
        # Upload a file
        await client.put_object("my-bucket", "hello.txt", b"Hello, World!")
        
        # Download it back
        response = await client.get_object("my-bucket", "hello.txt")
        content = response["body"]
        print(content.decode())  # Hello, World!

asyncio.run(main())
```

## Why S3 Asyncio Client?

- **Performance**: Async operations allow handling multiple S3 requests concurrently
- **Simplicity**: Clean, intuitive API without the complexity of boto3
- **Lightweight**: Minimal footprint with only essential dependencies
- **Modern**: Built for Python 3.11+ with modern async patterns
- **Flexible**: Works with any S3-compatible storage service

## Getting Started

Ready to start using S3 Asyncio Client? Check out our [Installation Guide](getting-started/installation.md) and [Quick Start Tutorial](getting-started/quickstart.md).

## License

This project is licensed under the MIT License.