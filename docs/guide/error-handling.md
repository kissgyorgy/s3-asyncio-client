# Error Handling

This guide covers comprehensive error handling strategies, exception hierarchy, retry patterns, and debugging techniques for the S3 Asyncio Client.

## Exception Hierarchy

The S3 Asyncio Client provides a structured exception hierarchy for different types of errors:

```
Exception
├── S3Error (base for all S3-related errors)
    ├── S3ClientError (4xx HTTP status codes)
    │   ├── S3NotFoundError (404 errors)
    │   ├── S3AccessDeniedError (403 errors)
    │   └── S3InvalidRequestError (400 errors)
    └── S3ServerError (5xx HTTP status codes)
```

### Exception Details

#### S3Error (Base Exception)

The base exception for all S3 operations, providing common attributes:

```python
from s3_asyncio_client.exceptions import S3Error

try:
    await client.get_object("bucket", "key")
except S3Error as e:
    print(f"Error message: {e.message}")
    print(f"HTTP status code: {e.status_code}")
    print(f"S3 error code: {e.error_code}")
    print(f"Full error: {e}")  # Formatted string representation
```

#### S3ClientError (4xx Errors)

Represents client-side errors (malformed requests, authentication issues, etc.):

```python
from s3_asyncio_client.exceptions import S3ClientError

try:
    await client.put_object("invalid-bucket-name!", "key", b"data")
except S3ClientError as e:
    if e.status_code == 400:
        print("Bad request - check bucket name, key, or parameters")
    elif e.status_code == 403:
        print("Access denied - check credentials and permissions")
    elif e.status_code == 404:
        print("Resource not found")
    else:
        print(f"Client error {e.status_code}: {e.message}")
```

#### S3NotFoundError (404 Errors)

Specific exception for missing resources:

```python
from s3_asyncio_client.exceptions import S3NotFoundError

try:
    response = await client.get_object("my-bucket", "nonexistent-file.txt")
except S3NotFoundError:
    print("File does not exist")
    # Handle missing file (create default, redirect, etc.)
    response = {"body": b"Default content", "metadata": {}}
```

#### S3AccessDeniedError (403 Errors)

Specific exception for permission-related errors:

```python
from s3_asyncio_client.exceptions import S3AccessDeniedError

try:
    await client.put_object("restricted-bucket", "file.txt", b"data")
except S3AccessDeniedError:
    print("Access denied - check:")
    print("1. AWS credentials are correct")
    print("2. IAM policy allows s3:PutObject")
    print("3. Bucket policy allows access")
    print("4. Bucket exists and you have access")
```

#### S3InvalidRequestError (400 Errors)

Specific exception for malformed requests:

```python
from s3_asyncio_client.exceptions import S3InvalidRequestError

try:
    await client.put_object("", "file.txt", b"data")  # Empty bucket name
except S3InvalidRequestError as e:
    print(f"Invalid request: {e.message}")
    print("Check request parameters for correct format")
```

#### S3ServerError (5xx Errors)

Represents server-side errors (AWS service issues, temporary outages):

```python
from s3_asyncio_client.exceptions import S3ServerError

try:
    await client.put_object("bucket", "file.txt", b"data")
except S3ServerError as e:
    print(f"Server error {e.status_code}: {e.message}")
    print("This is likely a temporary issue - consider retrying")
```

## Error Handling Patterns

### Basic Error Handling

Handle specific exceptions for different error scenarios:

```python
from s3_asyncio_client import S3Client
from s3_asyncio_client.exceptions import (
    S3NotFoundError,
    S3AccessDeniedError,
    S3InvalidRequestError,
    S3ClientError,
    S3ServerError,
    S3Error
)

async def handle_get_object(client, bucket, key):
    """Example of comprehensive error handling for get_object."""
    try:
        response = await client.get_object(bucket, key)
        return response
        
    except S3NotFoundError:
        print(f"Object {key} not found in bucket {bucket}")
        return None
        
    except S3AccessDeniedError:
        print(f"Access denied for {bucket}/{key}")
        print("Check your AWS credentials and IAM permissions")
        raise  # Re-raise to let caller handle
        
    except S3InvalidRequestError as e:
        print(f"Invalid request: {e.message}")
        print("Check bucket name and key format")
        raise
        
    except S3ClientError as e:
        print(f"Client error {e.status_code}: {e.message}")
        if e.status_code == 429:  # Rate limiting
            print("Rate limited - consider implementing backoff")
        raise
        
    except S3ServerError as e:
        print(f"Server error {e.status_code}: {e.message}")
        print("AWS service issue - consider retrying")
        raise
        
    except S3Error as e:
        print(f"Unexpected S3 error: {e}")
        raise
        
    except Exception as e:
        print(f"Non-S3 error (network, etc.): {e}")
        raise

# Usage
async with S3Client(access_key, secret_key, region) as client:
    result = await handle_get_object(client, "my-bucket", "important-file.txt")
    if result:
        print(f"Downloaded {len(result['body'])} bytes")
    else:
        print("File not found, using defaults")
```

### Conditional Error Handling

Handle errors differently based on the operation:

```python
async def safe_head_object(client, bucket, key):
    """Check if object exists without raising exceptions."""
    try:
        metadata = await client.head_object(bucket, key)
        return True, metadata
    except S3NotFoundError:
        return False, None
    except S3Error as e:
        print(f"Error checking object existence: {e}")
        return False, None

async def get_object_if_exists(client, bucket, key):
    """Download object only if it exists."""
    exists, metadata = await safe_head_object(client, bucket, key)
    
    if not exists:
        print(f"Object {key} does not exist")
        return None
    
    print(f"Object exists, size: {metadata['content_length']} bytes")
    
    try:
        return await client.get_object(bucket, key)
    except S3Error as e:
        print(f"Error downloading object: {e}")
        return None

# Usage
result = await get_object_if_exists(client, "bucket", "optional-file.txt")
if result:
    print("File downloaded successfully")
else:
    print("File not available")
```

### Bulk Operation Error Handling

Handle errors when performing multiple operations:

```python
import asyncio

async def upload_files_with_error_handling(client, bucket, files):
    """Upload multiple files with individual error handling."""
    results = []
    
    async def upload_single_file(file_info):
        key, data = file_info
        try:
            result = await client.put_object(bucket, key, data)
            return {"key": key, "success": True, "result": result, "error": None}
        except S3Error as e:
            return {"key": key, "success": False, "result": None, "error": str(e)}
        except Exception as e:
            return {"key": key, "success": False, "result": None, "error": f"Unexpected error: {e}"}
    
    # Upload all files concurrently
    tasks = [upload_single_file(file_info) for file_info in files]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    successful = [r for r in results if isinstance(r, dict) and r["success"]]
    failed = [r for r in results if isinstance(r, dict) and not r["success"]]
    exceptions = [r for r in results if isinstance(r, Exception)]
    
    print(f"Upload summary: {len(successful)} successful, {len(failed)} failed, {len(exceptions)} exceptions")
    
    for failure in failed:
        print(f"Failed to upload {failure['key']}: {failure['error']}")
    
    for exception in exceptions:
        print(f"Unexpected exception: {exception}")
    
    return {
        "successful": successful,
        "failed": failed,
        "exceptions": exceptions
    }

# Usage
files_to_upload = [
    ("file1.txt", b"content1"),
    ("file2.txt", b"content2"),
    ("invalid/key/with/问题", b"content3"),  # This might fail
]

results = await upload_files_with_error_handling(client, "my-bucket", files_to_upload)
```

## Retry Strategies

### Exponential Backoff Retry

Implement exponential backoff for transient errors:

```python
import asyncio
import random
from typing import TypeVar, Callable, Any

T = TypeVar('T')

async def retry_with_exponential_backoff(
    operation: Callable[[], Any],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple = None
) -> Any:
    """
    Retry an async operation with exponential backoff.
    
    Args:
        operation: Async function to retry
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation
        jitter: Add random jitter to delays
        retryable_exceptions: Tuple of exceptions that should trigger retry
    """
    if retryable_exceptions is None:
        retryable_exceptions = (S3ServerError, ConnectionError, TimeoutError)
    
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await operation()
            
        except Exception as e:
            last_exception = e
            
            # Don't retry on final attempt
            if attempt == max_retries:
                break
                
            # Check if exception is retryable
            if not isinstance(e, retryable_exceptions):
                # For S3 client errors, only retry on specific codes
                if isinstance(e, S3ClientError):
                    if e.status_code not in [408, 429, 503, 504]:  # Timeout, rate limit, service unavailable, gateway timeout
                        break
                else:
                    break
            
            # Calculate delay
            delay = min(base_delay * (exponential_base ** attempt), max_delay)
            
            # Add jitter
            if jitter:
                delay += random.uniform(0, delay * 0.1)
            
            print(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f} seconds...")
            await asyncio.sleep(delay)
    
    # All retries exhausted
    raise last_exception

# Usage examples
async def upload_with_retry(client, bucket, key, data):
    """Upload with automatic retry."""
    async def upload_operation():
        return await client.put_object(bucket, key, data)
    
    return await retry_with_exponential_backoff(
        upload_operation,
        max_retries=3,
        base_delay=1.0
    )

async def download_with_retry(client, bucket, key):
    """Download with automatic retry."""
    async def download_operation():
        return await client.get_object(bucket, key)
    
    return await retry_with_exponential_backoff(
        download_operation,
        max_retries=5,
        base_delay=0.5,
        retryable_exceptions=(S3ServerError, ConnectionError, TimeoutError, S3ClientError)
    )

# Usage
try:
    result = await upload_with_retry(client, "bucket", "file.txt", b"data")
    print("Upload successful after retries")
except Exception as e:
    print(f"Upload failed after all retries: {e}")
```

### Custom Retry Decorator

Create a reusable retry decorator:

```python
import functools
from typing import Type, Union

def s3_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    retryable_errors: tuple = None
):
    """Decorator for automatic S3 operation retries."""
    if retryable_errors is None:
        retryable_errors = (S3ServerError, ConnectionError, TimeoutError)
    
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_with_exponential_backoff(
                lambda: func(*args, **kwargs),
                max_retries=max_retries,
                base_delay=base_delay,
                retryable_exceptions=retryable_errors
            )
        return wrapper
    return decorator

# Usage
class S3Operations:
    def __init__(self, client):
        self.client = client
    
    @s3_retry(max_retries=3, base_delay=0.5)
    async def robust_upload(self, bucket, key, data):
        """Upload with automatic retry."""
        return await self.client.put_object(bucket, key, data)
    
    @s3_retry(max_retries=5, base_delay=1.0)
    async def robust_download(self, bucket, key):
        """Download with automatic retry."""
        return await self.client.get_object(bucket, key)
    
    @s3_retry(max_retries=2, base_delay=0.2)
    async def robust_head(self, bucket, key):
        """Head request with automatic retry."""
        return await self.client.head_object(bucket, key)

# Usage
async with S3Client(access_key, secret_key, region) as client:
    ops = S3Operations(client)
    
    try:
        result = await ops.robust_upload("bucket", "file.txt", b"data")
        print("Upload successful")
    except Exception as e:
        print(f"Upload failed after all retries: {e}")
```

### Circuit Breaker Pattern

Implement circuit breaker to prevent cascading failures:

```python
import time
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        expected_exception: Type[Exception] = S3ServerError
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    async def call(self, operation):
        """Execute operation through circuit breaker."""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time < self.timeout:
                raise Exception("Circuit breaker is OPEN")
            else:
                self.state = CircuitState.HALF_OPEN
        
        try:
            result = await operation()
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Reset circuit breaker on successful operation."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        """Handle failure."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

# Usage
class RobustS3Client:
    def __init__(self, client):
        self.client = client
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, timeout=30.0)
    
    async def safe_get_object(self, bucket, key):
        """Get object with circuit breaker protection."""
        try:
            return await self.circuit_breaker.call(
                lambda: self.client.get_object(bucket, key)
            )
        except Exception as e:
            if "Circuit breaker is OPEN" in str(e):
                print("Service temporarily unavailable due to repeated failures")
                return None
            raise

# Usage
robust_client = RobustS3Client(client)
result = await robust_client.safe_get_object("bucket", "file.txt")
```

## Debugging and Logging

### Enable Debug Logging

Configure logging to debug S3 operations:

```python
import logging
import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Enable aiohttp debug logging
logging.getLogger('aiohttp.client').setLevel(logging.DEBUG)

# Create custom logger for S3 operations
s3_logger = logging.getLogger('s3_operations')

async def logged_s3_operation(client, operation_name, func):
    """Wrapper to log S3 operations."""
    s3_logger.info(f"Starting {operation_name}")
    start_time = time.time()
    
    try:
        result = await func()
        duration = time.time() - start_time
        s3_logger.info(f"{operation_name} completed in {duration:.2f}s")
        return result
    except Exception as e:
        duration = time.time() - start_time
        s3_logger.error(f"{operation_name} failed after {duration:.2f}s: {e}")
        raise

# Usage
async with S3Client(access_key, secret_key, region) as client:
    result = await logged_s3_operation(
        client,
        "put_object",
        lambda: client.put_object("bucket", "file.txt", b"data")
    )
```

### Request/Response Debugging

Custom middleware to inspect HTTP requests and responses:

```python
import json
from aiohttp import ClientSession, TraceConfig, TraceRequestStartParams, TraceRequestEndParams

async def on_request_start(session, trace_config_ctx, params: TraceRequestStartParams):
    """Log request details."""
    print(f"Request: {params.method} {params.url}")
    print(f"Headers: {dict(params.headers)}")

async def on_request_end(session, trace_config_ctx, params: TraceRequestEndParams):
    """Log response details."""
    print(f"Response: {params.response.status}")
    print(f"Response Headers: {dict(params.response.headers)}")

# Create trace config
trace_config = TraceConfig()
trace_config.on_request_start.append(on_request_start)
trace_config.on_request_end.append(on_request_end)

# Create session with tracing
async with ClientSession(trace_configs=[trace_config]) as session:
    client = S3Client(access_key, secret_key, region)
    client._session = session
    
    # All requests will be logged
    await client.put_object("bucket", "debug-file.txt", b"debug data")
```

### Error Context Collection

Collect detailed error context for debugging:

```python
import traceback
import sys
from datetime import datetime

class S3ErrorContext:
    """Collect comprehensive error context."""
    
    @staticmethod
    def collect_context(operation, bucket, key, exception, client=None):
        """Collect detailed error context."""
        context = {
            "timestamp": datetime.utcnow().isoformat(),
            "operation": operation,
            "bucket": bucket,
            "key": key,
            "exception": {
                "type": type(exception).__name__,
                "message": str(exception),
                "traceback": traceback.format_exc()
            },
            "python_version": sys.version,
        }
        
        # Add S3-specific error info
        if hasattr(exception, 'status_code'):
            context["exception"]["status_code"] = exception.status_code
        if hasattr(exception, 'error_code'):
            context["exception"]["error_code"] = exception.error_code
        
        # Add client info
        if client:
            context["client"] = {
                "region": client.region,
                "endpoint_url": client.endpoint_url,
            }
        
        return context
    
    @staticmethod
    def log_error_context(context):
        """Log error context in a structured format."""
        print("=" * 80)
        print("S3 ERROR CONTEXT")
        print("=" * 80)
        print(json.dumps(context, indent=2, default=str))
        print("=" * 80)

# Usage wrapper
async def debug_s3_operation(client, operation_name, operation_func, bucket, key):
    """Execute S3 operation with comprehensive error logging."""
    try:
        return await operation_func()
    except Exception as e:
        context = S3ErrorContext.collect_context(
            operation_name, bucket, key, e, client
        )
        S3ErrorContext.log_error_context(context)
        raise

# Usage
try:
    result = await debug_s3_operation(
        client,
        "get_object",
        lambda: client.get_object("nonexistent-bucket", "file.txt"),
        "nonexistent-bucket",
        "file.txt"
    )
except Exception as e:
    print(f"Operation failed: {e}")
```

## Error Recovery Strategies

### Graceful Degradation

Provide fallback behavior when S3 operations fail:

```python
class S3WithFallback:
    def __init__(self, primary_client, fallback_client=None, local_cache_dir=None):
        self.primary = primary_client
        self.fallback = fallback_client
        self.cache_dir = local_cache_dir
    
    async def get_object_with_fallback(self, bucket, key):
        """Get object with multiple fallback strategies."""
        
        # Try primary S3 service
        try:
            return await self.primary.get_object(bucket, key)
        except S3Error as e:
            print(f"Primary S3 failed: {e}")
        
        # Try fallback S3 service
        if self.fallback:
            try:
                return await self.fallback.get_object(bucket, key)
            except S3Error as e:
                print(f"Fallback S3 failed: {e}")
        
        # Try local cache
        if self.cache_dir:
            cache_path = os.path.join(self.cache_dir, bucket, key)
            if os.path.exists(cache_path):
                with open(cache_path, "rb") as f:
                    return {
                        "body": f.read(),
                        "source": "local_cache",
                        "content_type": "application/octet-stream"
                    }
        
        # All fallbacks exhausted
        raise S3NotFoundError(f"Object {bucket}/{key} not available from any source")

# Usage
fallback_client = S3WithFallback(
    primary_client=S3Client(primary_access_key, primary_secret, region),
    fallback_client=S3Client(backup_access_key, backup_secret, region, endpoint_url="https://backup-s3.com"),
    local_cache_dir="/tmp/s3_cache"
)

try:
    result = await fallback_client.get_object_with_fallback("bucket", "important-file.txt")
    print(f"Retrieved from: {result.get('source', 'primary')}")
except S3NotFoundError:
    print("File not available from any source")
```

### Partial Failure Handling

Handle partial failures in batch operations:

```python
async def resilient_batch_upload(client, bucket, files, max_concurrent=5):
    """Upload files with partial failure handling."""
    successful_uploads = []
    failed_uploads = []
    
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def upload_with_semaphore(file_info):
        key, data = file_info
        async with semaphore:
            try:
                result = await client.put_object(bucket, key, data)
                return {"key": key, "success": True, "result": result}
            except Exception as e:
                return {"key": key, "success": False, "error": str(e)}
    
    # Execute all uploads
    tasks = [upload_with_semaphore(file_info) for file_info in files]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    
    # Categorize results
    for result in results:
        if result["success"]:
            successful_uploads.append(result)
        else:
            failed_uploads.append(result)
    
    # Retry failed uploads with different strategy
    if failed_uploads:
        print(f"Retrying {len(failed_uploads)} failed uploads...")
        retry_results = await retry_failed_uploads(client, bucket, failed_uploads)
        successful_uploads.extend(retry_results)
    
    return {
        "successful": len(successful_uploads),
        "failed": len(failed_uploads),
        "details": {
            "successful": successful_uploads,
            "failed": failed_uploads
        }
    }

async def retry_failed_uploads(client, bucket, failed_uploads):
    """Retry failed uploads with exponential backoff."""
    successful_retries = []
    
    for failed_upload in failed_uploads:
        key = failed_upload["key"]
        # Assume we can reconstruct data or have it cached
        try:
            result = await retry_with_exponential_backoff(
                lambda: client.put_object(bucket, key, b"retry_data"),
                max_retries=2,
                base_delay=2.0
            )
            successful_retries.append({"key": key, "success": True, "result": result})
        except Exception as e:
            print(f"Final failure for {key}: {e}")
    
    return successful_retries
```

## Testing Error Conditions

### Mock Error Responses

Test error handling with mocked responses:

```python
import pytest
from unittest.mock import AsyncMock, Mock
from s3_asyncio_client.exceptions import S3NotFoundError, S3AccessDeniedError

@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling with mocked responses."""
    client = S3Client("test-key", "test-secret", "us-east-1")
    
    # Mock a 404 response
    mock_response = Mock()
    mock_response.status = 404
    mock_response.text = AsyncMock(return_value="""
        <Error>
            <Code>NoSuchKey</Code>
            <Message>The specified key does not exist.</Message>
        </Error>
    """)
    
    client._make_request = AsyncMock(side_effect=S3NotFoundError("Object not found"))
    
    # Test that the exception is properly raised and handled
    with pytest.raises(S3NotFoundError):
        await client.get_object("test-bucket", "nonexistent-key")

@pytest.mark.asyncio
async def test_retry_logic():
    """Test retry logic with temporary failures."""
    client = S3Client("test-key", "test-secret", "us-east-1")
    
    # Mock responses: fail twice, then succeed
    call_count = 0
    async def mock_request(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise S3ServerError("Temporary server error", 500)
        
        # Success on third attempt
        mock_response = Mock()
        mock_response.headers = {"ETag": '"success"'}
        return mock_response
    
    client._make_request = AsyncMock(side_effect=mock_request)
    
    # Test with retry wrapper
    result = await retry_with_exponential_backoff(
        lambda: client.put_object("bucket", "key", b"data"),
        max_retries=3
    )
    
    assert call_count == 3  # Failed twice, succeeded on third attempt
```

## Best Practices Summary

### 1. Use Specific Exception Handling

```python
# Good: Handle specific exceptions
try:
    result = await client.get_object(bucket, key)
except S3NotFoundError:
    # Handle missing file
    pass
except S3AccessDeniedError:
    # Handle permission issue
    pass

# Avoid: Catching all exceptions
try:
    result = await client.get_object(bucket, key)
except Exception:
    # Too broad, might catch programming errors
    pass
```

### 2. Implement Appropriate Retry Logic

```python
# Retry server errors and network issues
retryable_errors = (S3ServerError, ConnectionError, TimeoutError)

# Don't retry client errors (except rate limiting)
non_retryable_errors = (S3NotFoundError, S3AccessDeniedError, S3InvalidRequestError)
```

### 3. Log Errors with Context

```python
# Good: Include operation context
try:
    await client.put_object(bucket, key, data)
except S3Error as e:
    logger.error(f"Failed to upload {key} to {bucket}: {e}", extra={
        "bucket": bucket,
        "key": key,
        "operation": "put_object",
        "error_code": getattr(e, 'error_code', None),
        "status_code": getattr(e, 'status_code', None)
    })
```

### 4. Provide Graceful Degradation

```python
# Provide fallback when possible
try:
    data = await client.get_object(bucket, key)
except S3NotFoundError:
    data = {"body": b"default content"}  # Fallback
except S3Error:
    data = None  # Let caller handle
```

## Next Steps

- Review [Performance Tips](performance.md) for optimization strategies
- Check [Advanced Usage](advanced-usage.md) for complex scenarios
- Browse [Examples](../examples/) for complete error handling examples
- See [API Reference](../reference/) for detailed exception documentation