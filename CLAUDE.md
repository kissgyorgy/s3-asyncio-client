# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Core Development Workflow
```bash
# Environment setup (using uv)
uv sync                          # Install all dependencies including dev dependencies
devenv shell                     # Enter devenv environment

# Testing
pytest                    # Run all tests
pytest tests/test_client.py::test_put_object  # Run specific test
pytest -v --tb=short     # Verbose output with short tracebacks

# Code Quality
ruff check               # Lint code
ruff format              # Format code
ruff check --fix         # Auto-fix linting issues

# Documentation
mkdocs serve                    # Local documentation server
mkdocs build                    # Build documentation
```

### Testing with Minio (S3-compatible service)
```bash
# Start local minio server for integration testing
minio server /tmp/minio-data --console-address :9001
# Default credentials: minioadmin/minioadmin
# Console: http://localhost:9001, API: http://localhost:9000
```

## Architecture Overview

### Core Components
- **S3Client** (`client.py`): Main async client with context manager pattern, single aiohttp session
- **AWSSignatureV4** (`auth.py`): Complete AWS Signature V4 implementation for authentication
- **Exception Hierarchy** (`exceptions.py`): Structured S3Error -> S3ClientError/S3ServerError

### Key Design Patterns
- **Async Context Manager**: All operations through `async with S3Client(...) as client:`
- **Unified Request Interface**: All operations via `_make_request()` with automatic signing and error handling
- **Builder Pattern**: `_build_url()` handles AWS S3 vs S3-compatible service URL differences

### Authentication Flow
1. Canonical request creation (normalize HTTP components)
2. String-to-sign generation (standardized signing payload)  
3. Signature calculation (HMAC-SHA256 with derived keys)
4. Authorization header creation (AWS4-HMAC-SHA256 format)

### Error Handling Strategy
- Parse XML error responses from S3 into structured exceptions
- Status code precedence over error codes for classification
- Specific exception types: S3NotFoundError (404), S3AccessDeniedError (403), S3InvalidRequestError (400)

## Testing Architecture

### Test Categories
- **Unit Tests**: Mock `_make_request()` to test logic without network calls
- **Integration Tests**: Use moto library to mock AWS S3 service
- **Authentication Tests**: Mock datetime for predictable signature generation

### Test Patterns
```python
# Integration test pattern  
@mock_s3
async def test_with_moto():
    # Real S3 operations against moto mock
```

- Never start required services like minio; always assume they are running.
  Ask the user to start them if not running.

## Key Implementation Details

### URL Building Logic
- **AWS S3**: Virtual hosted-style (`https://bucket.s3.region.amazonaws.com/key`)
- **S3-Compatible**: Path-style (`https://endpoint.com/bucket/key`)
- Automatic URL encoding for special characters


### Response Handling
- Extract metadata from `x-amz-meta-*` headers
- Parse XML error responses into structured exceptions
- Return consistent response format: `{"body": data, "metadata": {...}}`

## Development Notes

### When Adding New Operations
- Follow async/await pattern throughout
- Use `_make_request()` for all HTTP operations
- Implement both unit tests (mocked) and integration tests (moto)
- Add comprehensive docstrings with parameter and return type documentation

### Error Handling Requirements  
- Always parse S3 XML error responses
- Raise specific exception types based on error codes
- Gracefully handle malformed/non-XML error responses

### Authentication Considerations
- All requests must be signed via AWSSignatureV4
- Presigned URLs use query parameters instead of Authorization header
- Payload hashing required for request integrity

### Performance Patterns
- Single aiohttp session for connection pooling
- Async context managers for proper resource cleanup
