# Contributing

Thank you for your interest in contributing to S3 Asyncio Client! This guide will help you get started with development and understand our contribution process.

## Development Environment Setup

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- Git

### Setting Up the Development Environment

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/s3-asyncio-client.git
   cd s3-asyncio-client
   ```

2. **Install dependencies:**
   ```bash
   uv sync --dev
   ```

3. **Activate the virtual environment:**
   ```bash
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

4. **Verify installation:**
   ```bash
   uv run python -c "import s3_asyncio_client; print('Setup successful!')"
   ```

## Development Workflow

### Code Quality

We use several tools to maintain code quality:

- **ruff**: For linting and formatting
- **pytest**: For testing
- **mypy**: For type checking (optional but recommended)

### Running Code Quality Checks

```bash
# Format code
uv run ruff format

# Check for linting issues
uv run ruff check

# Fix auto-fixable issues
uv run ruff check --fix

# Run all checks before committing
uv run ruff check && uv run ruff format --check
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=s3_asyncio_client

# Run specific test file
uv run pytest tests/test_client.py

# Run tests with verbose output
uv run pytest -v

# Run tests and stop on first failure
uv run pytest -x
```

### Testing with MinIO

For integration testing, you can set up a local MinIO server:

```bash
# Start MinIO with Docker
docker run -p 9000:9000 -p 9001:9001 \
  -e "MINIO_ROOT_USER=minioadmin" \
  -e "MINIO_ROOT_PASSWORD=minioadmin" \
  minio/minio server /data --console-address ":9001"

# Run integration tests
export S3_TEST_ENDPOINT=http://localhost:9000
export S3_TEST_ACCESS_KEY=minioadmin
export S3_TEST_SECRET_KEY=minioadmin
uv run pytest tests/test_integration.py
```

## Project Structure

```
s3-asyncio-client/
├── src/s3_asyncio_client/
│   ├── __init__.py          # Public API exports
│   ├── client.py            # Main S3Client class
│   ├── auth.py              # AWS Signature V4 authentication
│   ├── exceptions.py        # Exception hierarchy
│   └── multipart.py         # Multipart upload functionality
├── tests/
│   ├── test_client.py       # Client tests
│   ├── test_auth.py         # Authentication tests
│   ├── test_exceptions.py   # Exception tests
│   ├── test_multipart.py    # Multipart upload tests
│   └── conftest.py          # Test configuration
├── docs/                    # Documentation
├── pyproject.toml           # Project configuration
└── README.md
```

## Contributing Guidelines

### Types of Contributions

We welcome several types of contributions:

1. **Bug Fixes**: Fix issues in existing functionality
2. **New Features**: Add new S3 operations or capabilities
3. **Documentation**: Improve docs, examples, or guides
4. **Tests**: Add or improve test coverage
5. **Performance**: Optimize existing code

### Before You Start

1. **Check existing issues**: Look for related issues or discussions
2. **Create an issue**: For significant changes, create an issue first to discuss
3. **Fork the repository**: Create your own fork to work on

### Making Changes

1. **Create a branch**: Use descriptive branch names
   ```bash
   git checkout -b feature/add-object-locking
   git checkout -b fix/multipart-progress-tracking
   git checkout -b docs/improve-error-handling-guide
   ```

2. **Make your changes**: Follow the coding standards below

3. **Add tests**: All new functionality must include tests

4. **Update documentation**: Update relevant documentation files

5. **Run quality checks**: Ensure all checks pass
   ```bash
   uv run ruff check --fix
   uv run ruff format
   uv run pytest
   ```

### Coding Standards

#### Code Style

- Use **ruff** for formatting and linting
- Follow **PEP 8** style guidelines
- Use **type hints** for all function parameters and return values
- Maximum line length: **88 characters**

#### Code Organization

```python
# Good: Clear type hints and docstrings
async def put_object(
    self, 
    bucket: str, 
    key: str, 
    data: bytes,
    content_type: str | None = None,
    metadata: dict[str, str] | None = None
) -> dict[str, Any]:
    """Upload an object to S3.
    
    Args:
        bucket: The S3 bucket name
        key: The object key
        data: The object data as bytes
        content_type: The MIME type of the object
        metadata: Custom metadata for the object
        
    Returns:
        A dictionary containing the response data
        
    Raises:
        S3ClientError: If the request fails
    """
```

#### Error Handling

- Use specific exception types from `exceptions.py`
- Provide helpful error messages
- Include relevant context in exceptions

```python
# Good: Specific exception with context
if response.status == 404:
    raise S3NotFoundError(
        f"Object '{key}' not found in bucket '{bucket}'",
        status_code=404
    )

# Avoid: Generic exceptions
if response.status == 404:
    raise Exception("Not found")
```

#### Async/Await Patterns

- Use `async`/`await` consistently
- Properly handle `aiohttp` sessions
- Use context managers where appropriate

```python
# Good: Proper async context management
async with self._session.get(url) as response:
    data = await response.read()
    return data

# Avoid: Not awaiting properly
response = self._session.get(url)  # Missing await
```

### Testing Guidelines

#### Test Structure

- Use **pytest** for all tests
- Use **pytest-asyncio** for async tests
- Mock external dependencies when appropriate

```python
import pytest
from unittest.mock import AsyncMock, Mock

@pytest.mark.asyncio
async def test_put_object_success(client):
    """Test successful object upload."""
    # Arrange
    mock_response = Mock()
    mock_response.headers = {"ETag": '"abc123"'}
    client._make_request = AsyncMock(return_value=mock_response)
    
    # Act
    result = await client.put_object("bucket", "key", b"data")
    
    # Assert
    assert result["etag"] == '"abc123"'
    client._make_request.assert_called_once()
```

#### Test Coverage

- Aim for **high test coverage** (>90%)
- Test both **success and error cases**
- Include **edge cases** and **boundary conditions**

### Documentation Guidelines

#### Docstring Style

Use **Google-style docstrings**:

```python
def function(param1: str, param2: int = 0) -> str:
    """Brief description of the function.
    
    Longer description if needed, explaining the purpose,
    behavior, and any important details.
    
    Args:
        param1: Description of param1
        param2: Description of param2, defaults to 0
        
    Returns:
        Description of the return value
        
    Raises:
        ValueError: If param1 is empty
        S3ClientError: If the S3 request fails
        
    Example:
        >>> result = function("hello", 42)
        >>> print(result)
        "hello42"
    """
```

#### Documentation Files

- Use **Markdown** for all documentation
- Include **code examples** in documentation
- Keep examples **practical** and **runnable**

### Submitting Changes

#### Pull Request Process

1. **Push your branch**: Push to your fork
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create a pull request**: Use the GitHub interface

3. **Fill out the PR template**: Provide a clear description

4. **Ensure CI passes**: All checks must pass

5. **Respond to feedback**: Address reviewer comments

#### PR Description Template

```markdown
## Summary

Brief description of the changes made.

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing

- [ ] Tests pass locally
- [ ] New tests added for new functionality
- [ ] Integration tests pass (if applicable)

## Checklist

- [ ] Code follows the project's style guidelines
- [ ] Self-review of code completed
- [ ] Code is commented, particularly in hard-to-understand areas
- [ ] Corresponding documentation changes made
- [ ] No new warnings introduced
```

## Release Process

### Versioning

We follow **Semantic Versioning** (SemVer):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create and push git tag
4. GitHub Actions will handle PyPI release

## Getting Help

### Communication

- **Issues**: For bug reports and feature requests
- **Discussions**: For questions and general discussion
- **Email**: For security issues (security@example.com)

### Development Questions

If you have questions while developing:

1. Check existing **documentation** and **examples**
2. Search **existing issues** and **discussions**
3. Create a **new discussion** for general questions
4. Create an **issue** for specific bugs or feature requests

## Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please:

- Be respectful and constructive in all interactions
- Focus on what is best for the community
- Show empathy towards other contributors
- Accept constructive criticism gracefully

## Recognition

Contributors will be recognized in:

- **CONTRIBUTORS.md** file
- **Release notes** for significant contributions
- **Documentation** for major feature additions

Thank you for contributing to S3 Asyncio Client! 🚀