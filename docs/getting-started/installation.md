# Installation

## Requirements

- Python 3.11 or higher
- `aiohttp` library (installed automatically)

## Install from PyPI

```bash
pip install s3-asyncio-client
```

## Install with uv (recommended)

If you're using [uv](https://github.com/astral-sh/uv) for package management:

```bash
uv add s3-asyncio-client
```

## Development Installation

To install for development with all optional dependencies:

```bash
git clone https://github.com/your-username/s3-asyncio-client.git
cd s3-asyncio-client
uv sync --dev
```

This will install:
- Core runtime dependencies
- Testing tools (pytest, pytest-asyncio, moto)
- Code quality tools (ruff)
- Documentation tools (mkdocs-material, mkdocstrings)

## Verify Installation

Test your installation by running:

```python
import asyncio
from s3_asyncio_client import S3Client

# This should not raise any import errors
print("S3 Asyncio Client installed successfully!")
```

## Next Steps

Once installed, head over to the [Quick Start Guide](quickstart.md) to learn how to configure and use the client.