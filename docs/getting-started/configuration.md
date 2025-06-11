# Configuration

This guide covers all the configuration options available for S3 Asyncio Client.

## Basic Configuration

### Required Parameters

```python
from s3_asyncio_client import S3Client

client = S3Client(
    access_key="your-access-key",    # AWS Access Key ID
    secret_key="your-secret-key",    # AWS Secret Access Key
    region="us-east-1"               # AWS Region
)
```

### Optional Parameters

```python
client = S3Client(
    access_key="your-access-key",
    secret_key="your-secret-key",
    region="us-east-1",
    endpoint_url="https://s3.amazonaws.com",  # Custom S3 endpoint
    session_token=None                        # AWS Session Token (for temporary credentials)
)
```

## Environment Variables

You can also configure the client using environment variables:

```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
export AWS_SESSION_TOKEN="your-session-token"  # Optional
export S3_ENDPOINT_URL="https://s3.amazonaws.com"  # Optional
```

```python
import os
from s3_asyncio_client import S3Client

client = S3Client(
    access_key=os.environ["AWS_ACCESS_KEY_ID"],
    secret_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    region=os.environ["AWS_DEFAULT_REGION"],
    endpoint_url=os.environ.get("S3_ENDPOINT_URL"),
    session_token=os.environ.get("AWS_SESSION_TOKEN")
)
```

## S3-Compatible Services

The client works with any S3-compatible service by setting a custom endpoint URL.

### MinIO

```python
client = S3Client(
    access_key="minioadmin",
    secret_key="minioadmin",
    region="us-east-1",  # MinIO requires a region, use any valid AWS region
    endpoint_url="http://localhost:9000"
)
```

### DigitalOcean Spaces

```python
client = S3Client(
    access_key="your-spaces-key",
    secret_key="your-spaces-secret",
    region="nyc3",
    endpoint_url="https://nyc3.digitaloceanspaces.com"
)
```

### Wasabi

```python
client = S3Client(
    access_key="your-wasabi-key",
    secret_key="your-wasabi-secret",
    region="us-east-1",
    endpoint_url="https://s3.wasabisys.com"
)
```

### Cloudflare R2

```python
client = S3Client(
    access_key="your-r2-key",
    secret_key="your-r2-secret",
    region="auto",  # R2 uses "auto" as the region
    endpoint_url="https://your-account-id.r2.cloudflarestorage.com"
)
```

## Authentication Methods

### IAM User Credentials

Standard AWS IAM user credentials:

```python
client = S3Client(
    access_key="AKIAIOSFODNN7EXAMPLE",
    secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    region="us-east-1"
)
```

### Temporary Credentials (STS)

For temporary credentials from AWS STS:

```python
client = S3Client(
    access_key="ASIAIOSFODNN7EXAMPLE",
    secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    session_token="AQoDYXdzEJr...<remainder of security token>",
    region="us-east-1"
)
```

### IAM Roles (EC2/Lambda)

When running on EC2 instances or Lambda functions with IAM roles, you can retrieve credentials from the instance metadata service or environment:

```python
import boto3

# Get credentials from boto3 (which handles IAM roles automatically)
session = boto3.Session()
credentials = session.get_credentials()

client = S3Client(
    access_key=credentials.access_key,
    secret_key=credentials.secret_key,
    session_token=credentials.token,
    region=session.region_name or "us-east-1"
)
```

## Advanced Configuration

### Custom Session Configuration

The client uses aiohttp internally. You can customize the underlying HTTP session by subclassing the client:

```python
import aiohttp
from s3_asyncio_client import S3Client

class CustomS3Client(S3Client):
    async def _ensure_session(self):
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=10)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector
            )

client = CustomS3Client(access_key, secret_key, region)
```

### Logging Configuration

Enable debug logging to troubleshoot issues:

```python
import logging

# Enable debug logging for the client
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("s3_asyncio_client")
logger.setLevel(logging.DEBUG)

# Now all HTTP requests and responses will be logged
```

## Configuration Best Practices

### 1. Use Environment Variables

Store sensitive credentials in environment variables rather than hardcoding them:

```python
import os
from s3_asyncio_client import S3Client

client = S3Client(
    access_key=os.environ["AWS_ACCESS_KEY_ID"],
    secret_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    region=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
)
```

### 2. Use Context Managers

Always use async context managers to ensure proper cleanup:

```python
async with S3Client(access_key, secret_key, region) as client:
    # Your code here
    pass
# Client is automatically closed
```

### 3. Handle Different Environments

Create a configuration function that handles different environments:

```python
import os
from s3_asyncio_client import S3Client

def create_s3_client():
    if os.environ.get("ENVIRONMENT") == "development":
        # Use MinIO for local development
        return S3Client(
            access_key="minioadmin",
            secret_key="minioadmin",
            region="us-east-1",
            endpoint_url="http://localhost:9000"
        )
    else:
        # Use AWS S3 for production
        return S3Client(
            access_key=os.environ["AWS_ACCESS_KEY_ID"],
            secret_key=os.environ["AWS_SECRET_ACCESS_KEY"],
            region=os.environ["AWS_DEFAULT_REGION"]
        )

async def main():
    async with create_s3_client() as client:
        # Your application code
        pass
```

### 4. Validate Configuration

Add validation to catch configuration errors early:

```python
import os
from s3_asyncio_client import S3Client

def validate_config():
    required_vars = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]
    missing = [var for var in required_vars if not os.environ.get(var)]
    if missing:
        raise ValueError(f"Missing required environment variables: {missing}")

def create_s3_client():
    validate_config()
    return S3Client(
        access_key=os.environ["AWS_ACCESS_KEY_ID"],
        secret_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    )
```

## Next Steps

Now that you have your client configured, learn about:

- [Basic Operations](../guide/basic-operations.md) - Core S3 operations
- [Error Handling](../guide/error-handling.md) - Handling different types of errors
- [Examples](../examples/basic.md) - Practical usage examples