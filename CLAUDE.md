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
mkdocs build                    # Build documentation
```

### Testing with Minio (S3-compatible service)
```bash
# Start local minio server for integration testing
minio server tmp/minio-data --console-address :9001
# Default credentials: minioadmin/minioadmin
# Console: http://localhost:9001, API: http://localhost:9000
```

## Architecture Overview

### Core Components
- **S3Client** (`client.py`): Main async client with context manager pattern, single aiohttp session
- **_MultipartOperations** (`multipart.py`): Handling multipart upload logic
- **_ObjectOperations** (`objects.py`): Handling object-related operations like put, get, delete
- **_BucketOperations** (`buckets.py`): Handling bucket-related operations like create bucket, list objects
- **AWSSignatureV4** (`auth.py`): Complete AWS Signature V4 implementation for authentication
- **Exception Hierarchy** (`exceptions.py`): Structured S3Error -> S3ClientError/S3ServerError

### Key Design Patterns
- **Async Context Manager**: All operations through `async with S3Client(...) as client:`
- **Unified Request Interface**: All operations via `_make_request()` with automatic signing and error handling

### Authentication Flow
1. Canonical request creation (normalize HTTP components)
2. String-to-sign generation (standardized signing payload)  
3. Signature calculation (HMAC-SHA256 with derived keys)
4. Authorization header creation (AWS4-HMAC-SHA256 format)

### Error Handling Strategy
- Parse XML error responses from S3 into structured exceptions
- Status code precedence over error codes for classification
- Specific exception types: `S3NotFoundError` (404), `S3AccessDeniedError` (403), `S3InvalidRequestError` (400)

## Testing Architecture

### Test Categories
- **Unit Tests**: `mock_client` pytest fixture mock `_make_request()` to test logic without network calls
- **Authentication Tests**: Mock datetime for predictable signature generation

### Testing
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
- Implement both unit tests (`mock_client`) and integration tests

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
