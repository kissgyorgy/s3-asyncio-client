"""Minimal asyncio S3 client library."""

__version__ = "0.1.0"

from .client import S3Client
from .exceptions import (
    S3AccessDeniedError,
    S3ClientError,
    S3Error,
    S3InvalidRequestError,
    S3NotFoundError,
    S3ServerError,
)

__all__ = [
    "S3Client",
    "S3Error",
    "S3ClientError",
    "S3ServerError",
    "S3NotFoundError",
    "S3AccessDeniedError",
    "S3InvalidRequestError",
]
