# Testing

This guide covers the testing infrastructure and practices for S3 Asyncio Client.

## Overview

Our testing strategy includes:

- **Unit Tests**: Test individual functions and classes in isolation
- **Integration Tests**: Test interactions with real S3 services
- **Mock Tests**: Test behavior with simulated responses
- **Performance Tests**: Verify performance characteristics

## Test Structure

```
tests/
├── conftest.py              # Test configuration and fixtures
├── test_client.py           # S3Client tests
├── test_auth.py             # Authentication tests
├── test_exceptions.py       # Exception tests
├── test_multipart.py        # Multipart upload tests
├── integration/
│   ├── test_s3_integration.py      # AWS S3 integration tests
│   └── test_minio_integration.py   # MinIO integration tests
└── performance/
    └── test_performance.py  # Performance benchmarks
```

## Running Tests

### Basic Test Execution

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_client.py

# Run specific test function
uv run pytest tests/test_client.py::test_client_initialization

# Stop on first failure
uv run pytest -x

# Run tests in parallel (install pytest-xdist)
uv run pytest -n auto
```

### Test Coverage

```bash
# Run tests with coverage report
uv run pytest --cov=s3_asyncio_client

# Generate HTML coverage report
uv run pytest --cov=s3_asyncio_client --cov-report=html

# Set minimum coverage threshold
uv run pytest --cov=s3_asyncio_client --cov-fail-under=90
```

### Test Selection

```bash
# Run only unit tests (exclude integration)
uv run pytest -m "not integration"

# Run only integration tests
uv run pytest -m integration

# Run only performance tests
uv run pytest -m performance

# Run tests matching pattern
uv run pytest -k "multipart"
```

## Test Categories

### Unit Tests

Unit tests focus on testing individual components in isolation using mocks.

```python
# tests/test_client.py
import pytest
from unittest.mock import AsyncMock, Mock
from s3_asyncio_client import S3Client

@pytest.mark.asyncio
async def test_put_object_success():
    """Test successful object upload."""
    client = S3Client("key", "secret", "us-east-1")
    
    # Mock the HTTP response
    mock_response = Mock()
    mock_response.status = 200
    mock_response.headers = {"ETag": '"abc123"'}
    mock_response.read = AsyncMock(return_value=b"")
    
    client._make_request = AsyncMock(return_value=mock_response)
    
    # Test the operation
    result = await client.put_object("bucket", "key", b"data")
    
    assert result["etag"] == '"abc123"'
    client._make_request.assert_called_once()
    
    await client.close()
```

### Integration Tests

Integration tests verify behavior against real S3 services.

```python
# tests/integration/test_s3_integration.py
import pytest
import os
from s3_asyncio_client import S3Client, S3NotFoundError

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_object_lifecycle():
    """Test complete object lifecycle with real S3."""
    if not all([
        os.environ.get("AWS_ACCESS_KEY_ID"),
        os.environ.get("AWS_SECRET_ACCESS_KEY"),
        os.environ.get("S3_TEST_BUCKET")
    ]):
        pytest.skip("AWS credentials not configured")
    
    async with S3Client(
        os.environ["AWS_ACCESS_KEY_ID"],
        os.environ["AWS_SECRET_ACCESS_KEY"],
        os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    ) as client:
        bucket = os.environ["S3_TEST_BUCKET"]
        key = "test-integration-object.txt"
        content = b"Integration test content"
        
        try:
            # Upload object
            await client.put_object(bucket, key, content)
            
            # Verify upload
            response = await client.head_object(bucket, key)
            assert response["content_length"] == len(content)
            
            # Download object
            response = await client.get_object(bucket, key)
            assert response["body"] == content
            
            # List objects
            response = await client.list_objects(bucket, prefix="test-")
            keys = [obj["key"] for obj in response.get("contents", [])]
            assert key in keys
            
        finally:
            # Cleanup
            try:
                await client.delete_object(bucket, key)
            except S3NotFoundError:
                pass  # Already deleted
```

## Test Configuration

### Fixtures

Common fixtures are defined in `conftest.py`:

```python
# tests/conftest.py
import pytest
from s3_asyncio_client import S3Client

@pytest.fixture
def client():
    """Create S3Client for testing."""
    return S3Client("test-key", "test-secret", "us-east-1")

@pytest.fixture
async def async_client():
    """Create async S3Client with cleanup."""
    client = S3Client("test-key", "test-secret", "us-east-1")
    yield client
    await client.close()

@pytest.fixture
def minio_client():
    """Create client for MinIO testing."""
    return S3Client(
        "minioadmin",
        "minioadmin", 
        "us-east-1",
        endpoint_url="http://localhost:9000"
    )

@pytest.fixture
def mock_successful_response():
    """Mock successful HTTP response."""
    from unittest.mock import Mock, AsyncMock
    
    response = Mock()
    response.status = 200
    response.headers = {"ETag": '"test-etag"'}
    response.read = AsyncMock(return_value=b"test content")
    response.text = AsyncMock(return_value="<xml>success</xml>")
    return response
```

### Pytest Configuration

Configuration in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
asyncio_mode = "auto"
markers = [
    "integration: marks tests as integration tests",
    "performance: marks tests as performance tests",
    "slow: marks tests as slow running",
]
```

## Testing Patterns

### Async Testing

```python
@pytest.mark.asyncio
async def test_async_operation():
    """Test async operation."""
    async with S3Client("key", "secret", "region") as client:
        # Mock the request
        client._make_request = AsyncMock(return_value=mock_response)
        
        # Test the operation
        result = await client.get_object("bucket", "key")
        
        assert result is not None
```

### Exception Testing

```python
from s3_asyncio_client import S3NotFoundError

@pytest.mark.asyncio
async def test_object_not_found():
    """Test 404 error handling."""
    client = S3Client("key", "secret", "region")
    
    # Mock 404 response
    mock_response = Mock()
    mock_response.status = 404
    mock_response.text = AsyncMock(return_value="<Error><Code>NoSuchKey</Code></Error>")
    
    client._make_request = AsyncMock(return_value=mock_response)
    
    with pytest.raises(S3NotFoundError):
        await client.get_object("bucket", "nonexistent-key")
    
    await client.close()
```

### Parametrized Testing

```python
@pytest.mark.parametrize("bucket,key,expected", [
    ("test-bucket", "file.txt", "https://test-bucket.s3.us-east-1.amazonaws.com/file.txt"),
    ("bucket-2", "path/to/file.pdf", "https://bucket-2.s3.us-east-1.amazonaws.com/path/to/file.pdf"),
    ("special", "file with spaces.txt", "https://special.s3.us-east-1.amazonaws.com/file%20with%20spaces.txt"),
])
def test_url_building(client, bucket, key, expected):
    """Test URL building with various inputs."""
    url = client._build_url(bucket, key)
    assert url == expected
```

### Mock Patterns

```python
from unittest.mock import AsyncMock, Mock, patch

@pytest.mark.asyncio
async def test_with_session_mock():
    """Test with mocked aiohttp session."""
    client = S3Client("key", "secret", "region")
    
    with patch.object(client, '_session') as mock_session:
        mock_response = Mock()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.read = AsyncMock(return_value=b"data")
        
        mock_session.put.return_value.__aenter__.return_value = mock_response
        
        await client._ensure_session()
        result = await client.put_object("bucket", "key", b"data")
        
        mock_session.put.assert_called_once()
    
    await client.close()
```

## Integration Testing Setup

### AWS S3 Testing

For AWS S3 integration tests, set these environment variables:

```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
export S3_TEST_BUCKET="your-test-bucket"

# Run integration tests
uv run pytest -m integration
```

### MinIO Testing

Set up local MinIO for testing:

```bash
# Start MinIO with Docker
docker run -d -p 9000:9000 -p 9001:9001 \
  --name minio-test \
  -e "MINIO_ROOT_USER=minioadmin" \
  -e "MINIO_ROOT_PASSWORD=minioadmin" \
  minio/minio server /data --console-address ":9001"

# Set environment variables
export MINIO_ENDPOINT="http://localhost:9000"
export MINIO_ACCESS_KEY="minioadmin"
export MINIO_SECRET_KEY="minioadmin"

# Run MinIO integration tests
uv run pytest tests/integration/test_minio_integration.py
```

### Test Bucket Setup

Create test buckets for integration testing:

```python
# tests/integration/conftest.py
import pytest
import os
from s3_asyncio_client import S3Client

@pytest.fixture(scope="session")
async def test_bucket():
    """Create and cleanup test bucket."""
    if not os.environ.get("AWS_ACCESS_KEY_ID"):
        pytest.skip("AWS credentials not configured")
    
    bucket_name = f"s3-asyncio-test-{int(time.time())}"
    
    async with S3Client(
        os.environ["AWS_ACCESS_KEY_ID"],
        os.environ["AWS_SECRET_ACCESS_KEY"],
        os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    ) as client:
        # Create bucket for testing
        await client.create_bucket(bucket_name)
        
        yield bucket_name
        
        # Cleanup bucket after tests
        try:
            # Delete all objects first
            response = await client.list_objects(bucket_name)
            for obj in response.get("contents", []):
                await client.delete_object(bucket_name, obj["key"])
            
            # Delete bucket
            await client.delete_bucket(bucket_name)
        except Exception as e:
            print(f"Cleanup failed: {e}")
```

## Performance Testing

### Basic Performance Tests

```python
# tests/performance/test_performance.py
import pytest
import time
import asyncio
from s3_asyncio_client import S3Client

@pytest.mark.performance
@pytest.mark.asyncio
async def test_upload_performance():
    """Test upload performance."""
    if not os.environ.get("PERFORMANCE_TEST_ENABLED"):
        pytest.skip("Performance tests disabled")
    
    async with S3Client(
        os.environ["AWS_ACCESS_KEY_ID"],
        os.environ["AWS_SECRET_ACCESS_KEY"],
        os.environ["AWS_DEFAULT_REGION"]
    ) as client:
        bucket = os.environ["S3_TEST_BUCKET"]
        
        # Test data
        data_sizes = [1024, 10240, 102400, 1048576]  # 1KB, 10KB, 100KB, 1MB
        
        for size in data_sizes:
            data = b"x" * size
            key = f"perf-test-{size}-bytes.bin"
            
            start_time = time.time()
            await client.put_object(bucket, key, data)
            end_time = time.time()
            
            duration = end_time - start_time
            throughput = size / duration / 1024  # KB/s
            
            print(f"Upload {size} bytes: {duration:.3f}s ({throughput:.1f} KB/s)")
            
            # Cleanup
            await client.delete_object(bucket, key)
```

### Concurrent Performance Tests

```python
@pytest.mark.performance
@pytest.mark.asyncio
async def test_concurrent_uploads():
    """Test concurrent upload performance."""
    async with S3Client(
        os.environ["AWS_ACCESS_KEY_ID"],
        os.environ["AWS_SECRET_ACCESS_KEY"],
        os.environ["AWS_DEFAULT_REGION"]
    ) as client:
        bucket = os.environ["S3_TEST_BUCKET"]
        
        # Create tasks for concurrent uploads
        tasks = []
        data = b"test data" * 1000  # 9KB
        
        start_time = time.time()
        
        for i in range(10):
            key = f"concurrent-test-{i}.bin"
            task = client.put_object(bucket, key, data)
            tasks.append(task)
        
        # Wait for all uploads to complete
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"10 concurrent uploads: {duration:.3f}s")
        
        # Cleanup
        cleanup_tasks = []
        for i in range(10):
            key = f"concurrent-test-{i}.bin"
            cleanup_tasks.append(client.delete_object(bucket, key))
        
        await asyncio.gather(*cleanup_tasks)
```

## Testing Best Practices

### 1. Test Organization

- **Group related tests** in the same file
- **Use descriptive test names** that explain what is being tested
- **Keep tests focused** on a single behavior

### 2. Mock Strategy

- **Mock external dependencies** (HTTP requests, file system)
- **Test both success and failure paths**
- **Use specific assertions** rather than generic ones

### 3. Async Testing

- **Always use `@pytest.mark.asyncio`** for async tests
- **Properly close clients** to avoid warnings
- **Use `AsyncMock`** for async mocked methods

### 4. Test Data

- **Use meaningful test data** that reflects real usage
- **Test edge cases** (empty strings, large files, special characters)
- **Clean up test resources** after each test

### 5. Performance Considerations

- **Skip expensive tests** in regular runs
- **Use markers** to categorize tests
- **Mock time-consuming operations** in unit tests

## Continuous Integration

### GitHub Actions Configuration

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    
    steps:
    - uses: actions/checkout@v4
    - name: Install uv
      uses: astral-sh/setup-uv@v1
    - name: Set up Python
      run: uv python install ${{ matrix.python-version }}
    - name: Install dependencies
      run: uv sync --dev
    - name: Run linting
      run: uv run ruff check
    - name: Run formatting check
      run: uv run ruff format --check
    - name: Run tests
      run: uv run pytest --cov=s3_asyncio_client
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

## Debugging Tests

### Debug Configuration

```python
# Enable debug logging during tests
import logging
logging.basicConfig(level=logging.DEBUG)

# Or use pytest fixtures
@pytest.fixture
def debug_logging():
    logging.getLogger("s3_asyncio_client").setLevel(logging.DEBUG)
    logging.getLogger("aiohttp").setLevel(logging.DEBUG)
```

### Debugging Failed Tests

```bash
# Run with detailed output
uv run pytest -vvv --tb=long

# Drop into debugger on failure
uv run pytest --pdb

# Show local variables in traceback
uv run pytest --tb=auto -l

# Run specific failing test
uv run pytest tests/test_client.py::test_specific_function -vvv
```

## Test Maintenance

### Regular Maintenance Tasks

1. **Update test dependencies** regularly
2. **Review and update integration test credentials**
3. **Monitor test execution time** and optimize slow tests
4. **Ensure high test coverage** is maintained
5. **Review and update mock responses** to match real API responses

### Test Documentation

- Document **test setup requirements**
- Explain **integration test configuration**
- Provide **troubleshooting guides** for common test issues
- Keep **test examples** up to date

This comprehensive testing guide ensures that S3 Asyncio Client maintains high quality and reliability through thorough testing practices.