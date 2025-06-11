# S3 Asyncio Client

A minimal, fast, and simple asyncio-based Amazon S3 client library for Python.

## Features

- **Asyncio-native**: Built from the ground up for async/await patterns
- **Minimal dependencies**: Only requires `aiohttp`
- **Simple API**: Clean, intuitive interface without boto3 complexity
- **Full S3 compatibility**: Implements AWS Signature Version 4 authentication
- **Complete feature set**: All essential S3 operations supported

## Supported Operations

- `put_object` - Upload objects with metadata and content types
- `get_object` - Download objects with full metadata extraction
- `head_object` - Get object metadata without downloading
- `list_objects` - List bucket contents with pagination
- `generate_presigned_url` - Create signed URLs for temporary access
- `upload_file_multipart` - Efficient multipart uploads for large files

## Installation

```bash
uv add s3-asyncio-client
```

## Quick Start

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
        await client.put_object(
            bucket="my-bucket",
            key="hello.txt", 
            data=b"Hello, World!",
            content_type="text/plain"
        )
        
        # Download a file
        result = await client.get_object("my-bucket", "hello.txt")
        print(result["body"])  # b"Hello, World!"
        
        # List objects
        objects = await client.list_objects("my-bucket")
        for obj in objects["objects"]:
            print(f"{obj['key']} - {obj['size']} bytes")
        
        # Generate presigned URL
        url = client.generate_presigned_url(
            "GET", "my-bucket", "hello.txt", expires_in=3600
        )
        print(f"Download URL: {url}")

asyncio.run(main())
```

## Requirements

- Python 3.11+
- aiohttp 3.9+

## Development

```bash
# Setup
uv sync

# Run tests  
uv run pytest

# Format code
uv run ruff format .

# Lint code
uv run ruff check .
```

## License

MIT License