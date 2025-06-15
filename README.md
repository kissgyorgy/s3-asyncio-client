# S3 Asyncio Client

[![Tests](https://github.com/kissgyorgy/s3-asyncio-client/actions/workflows/test.yml/badge.svg)](https://github.com/kissgyorgy/s3-asyncio-client/actions/workflows/test.yml)
[![Documentation](https://github.com/kissgyorgy/s3-asyncio-client/actions/workflows/docs.yml/badge.svg)](https://kissgyorgy.github.io/s3-asyncio-client/)
[![PyPI version](https://badge.fury.io/py/s3-asyncio-client.svg)](https://badge.fury.io/py/s3-asyncio-client)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

A minimal, fast, and simple asyncio-based Amazon S3 client library for Python.

## Features

- 🚀 **Async/Await Support**: Built from the ground up with asyncio for non-blocking I/O operations
- 📦 **Minimal Dependencies**: Only requires `aiohttp` for HTTP operations
- 🔗 **S3 Compatible**: Works with Amazon S3 and S3-compatible services (MinIO, DigitalOcean Spaces, etc.)
- 🔐 **Full Authentication**: Complete AWS Signature Version 4 implementation
- 🔗 **Pre-signed URLs**: Generate time-limited URLs for secure access
- 🎯 **Type Safe**: Full type hints throughout the codebase
- ⚡ **High Performance**: Optimized for speed and memory efficiency

## Core Operations

| Operation | Description |
|-----------|-------------|
| `put_object` | Upload files and data to S3 |
| `get_object` | Download files and data from S3 |
| `head_object` | Get object metadata without downloading content |
| `list_objects` | List objects in a bucket with optional filtering |
| `generate_presigned_url` | Create secure, time-limited URLs |

## Installation

```bash
pip install s3-asyncio-client
```

Or with uv:

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
        await client.put_object("my-bucket", "hello.txt", b"Hello, World!")
        
        # Download it back
        response = await client.get_object("my-bucket", "hello.txt")
        content = response["body"]
        print(content.decode())  # Hello, World!

asyncio.run(main())
```

## Documentation

📖 **[Full Documentation](https://kissgyorgy.github.io/s3-asyncio-client/)**

- [Installation Guide](https://kissgyorgy.github.io/s3-asyncio-client/getting-started/installation/)
- [Quick Start Tutorial](https://kissgyorgy.github.io/s3-asyncio-client/getting-started/quickstart/)
- [API Reference](https://kissgyorgy.github.io/s3-asyncio-client/reference/)
- [Examples](https://kissgyorgy.github.io/s3-asyncio-client/examples/)
- [Performance Guide](https://kissgyorgy.github.io/s3-asyncio-client/guide/performance/)

## Advanced Example

```python
import asyncio
from s3_asyncio_client import S3Client, S3NotFoundError

async def advanced_example():
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key", 
        region="us-east-1"
    ) as client:
        bucket = "my-bucket"
        
        # Upload with metadata
        await client.put_object(
            bucket=bucket,
            key="document.pdf",
            data=pdf_content,
            content_type="application/pdf",
            metadata={"author": "John Doe", "version": "1.0"}
        )
        
        # Check if file exists
        try:
            info = await client.head_object(bucket, "document.pdf")
            print(f"File size: {info['content_length']} bytes")
        except S3NotFoundError:
            print("File not found!")
        
        # Generate presigned URL (valid for 1 hour)
        url = client.generate_presigned_url(
            method="GET", 
            bucket=bucket, 
            key="document.pdf",
            expires_in=3600
        )
        print(f"Download URL: {url}")

asyncio.run(advanced_example())
```

## S3-Compatible Services

Works with any S3-compatible service:

```python
# MinIO
client = S3Client(
    access_key="minioadmin",
    secret_key="minioadmin",
    region="us-east-1",
    endpoint_url="http://localhost:9000"
)

# DigitalOcean Spaces
client = S3Client(
    access_key="your-spaces-key",
    secret_key="your-spaces-secret", 
    region="nyc3",
    endpoint_url="https://nyc3.digitaloceanspaces.com"
)
```

## Requirements

- Python 3.11+
- aiohttp 3.9+

## Development

```bash
# Clone the repository
git clone https://github.com/kissgyorgy/s3-asyncio-client.git
cd s3-asyncio-client

# Setup with uv (recommended)
uv sync --dev

# Run tests  
uv run pytest

# Format code
uv run ruff format

# Lint code
uv run ruff check
```

## Contributing

We welcome contributions! Please see our [Contributing Guide](https://kissgyorgy.github.io/s3-asyncio-client/development/contributing/) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.