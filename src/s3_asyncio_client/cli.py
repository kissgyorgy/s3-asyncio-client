#!/usr/bin/env python3
"""S3 CLI interface using the s3-asyncio-client library."""

import asyncio
import json
import os
import sys

import click

from .client import S3Client


def get_client_from_env():
    """Create S3Client from environment variables."""
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    endpoint_url = os.getenv("AWS_ENDPOINT_URL")

    if not access_key or not secret_key:
        click.echo(
            "Error: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set", err=True
        )
        sys.exit(1)

    return S3Client(
        access_key=access_key,
        secret_key=secret_key,
        region=region,
        endpoint_url=endpoint_url,
    )


@click.group()
def cli():
    """S3 CLI - A command line interface for S3 operations."""
    pass


@cli.command()
@click.argument("bucket")
@click.argument("key")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--content-type", help="Content type of the object")
@click.option("--metadata", help="JSON string of metadata key-value pairs")
def put(bucket, key, file_path, content_type, metadata):
    """Upload a file to S3."""

    async def _put():
        client = get_client_from_env()

        # Read file data
        with open(file_path, "rb") as f:
            data = f.read()

        # Parse metadata if provided
        metadata_dict = None
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
            except json.JSONDecodeError:
                click.echo("Error: Invalid JSON in metadata", err=True)
                return

        async with client:
            result = await client.put_object(
                bucket=bucket,
                key=key,
                data=data,
                content_type=content_type,
                metadata=metadata_dict,
            )

        click.echo("Upload successful!")
        click.echo(f"ETag: {result['etag']}")
        if result.get("version_id"):
            click.echo(f"Version ID: {result['version_id']}")

    asyncio.run(_put())


@cli.command()
@click.argument("bucket")
@click.argument("key")
@click.argument("output_path", type=click.Path())
def get(bucket, key, output_path):
    """Download a file from S3."""

    async def _get():
        client = get_client_from_env()

        async with client:
            result = await client.get_object(bucket=bucket, key=key)

        # Write to output file
        with open(output_path, "wb") as f:
            f.write(result["body"])

        click.echo("Download successful!")
        click.echo(f"Content Type: {result.get('content_type', 'N/A')}")
        click.echo(f"Content Length: {result['content_length']} bytes")
        click.echo(f"ETag: {result['etag']}")
        click.echo(f"Last Modified: {result.get('last_modified', 'N/A')}")

        if result["metadata"]:
            click.echo("Metadata:")
            for k, v in result["metadata"].items():
                click.echo(f"  {k}: {v}")

    asyncio.run(_get())


@cli.command()
@click.argument("bucket")
@click.argument("key")
def head(bucket, key):
    """Get object metadata without downloading."""

    async def _head():
        client = get_client_from_env()

        async with client:
            result = await client.head_object(bucket=bucket, key=key)

        click.echo(f"Object: s3://{bucket}/{key}")
        click.echo(f"Content Type: {result.get('content_type', 'N/A')}")
        click.echo(f"Content Length: {result['content_length']} bytes")
        click.echo(f"ETag: {result['etag']}")
        click.echo(f"Last Modified: {result.get('last_modified', 'N/A')}")

        if result.get("version_id"):
            click.echo(f"Version ID: {result['version_id']}")

        if result["metadata"]:
            click.echo("Metadata:")
            for k, v in result["metadata"].items():
                click.echo(f"  {k}: {v}")

    asyncio.run(_head())


@cli.command()
@click.argument("bucket")
@click.option("--prefix", help="Object key prefix filter")
@click.option("--max-keys", default=1000, help="Maximum number of objects to return")
def list(bucket, prefix, max_keys):
    """List objects in a bucket."""

    async def _list():
        client = get_client_from_env()

        async with client:
            result = await client.list_objects(
                bucket=bucket, prefix=prefix, max_keys=max_keys
            )

        if not result["objects"]:
            click.echo("No objects found")
            return

        click.echo(f"Bucket: {bucket}")
        if prefix:
            click.echo(f"Prefix: {prefix}")
        click.echo(f"Objects ({len(result['objects'])}):")
        click.echo()

        for obj in result["objects"]:
            size_mb = obj["size"] / (1024 * 1024)
            click.echo(f"{obj['last_modified'][:19]} {size_mb:>8.2f} MB  {obj['key']}")

        if result["is_truncated"]:
            click.echo("\n... (truncated, use --max-keys to see more)")

    asyncio.run(_list())


@cli.command()
@click.argument("method")
@click.argument("bucket")
@click.argument("key")
@click.option("--expires-in", default=3600, help="URL expiration time in seconds")
def presigned_url(method, bucket, key, expires_in):
    """Generate a presigned URL for S3 operations."""
    client = get_client_from_env()

    url = client.generate_presigned_url(
        method=method.upper(), bucket=bucket, key=key, expires_in=expires_in
    )

    click.echo(url)


@cli.command()
@click.argument("bucket")
@click.argument("key")
def delete(bucket, key):
    """Delete an object from S3."""

    async def _delete():
        client = get_client_from_env()

        async with client:
            result = await client.delete_object(bucket=bucket, key=key)

        click.echo("Delete successful!")
        if result.get("version_id"):
            click.echo(f"Version ID: {result['version_id']}")
        if result.get("delete_marker"):
            click.echo("Delete marker created")

    asyncio.run(_delete())


@cli.command()
@click.argument("bucket")
def create_bucket(bucket):
    """Create a new S3 bucket."""

    async def _create_bucket():
        client = get_client_from_env()

        async with client:
            result = await client.create_bucket(bucket=bucket)

        click.echo("Bucket created successfully!")
        if result.get("location"):
            click.echo(f"Location: {result['location']}")

    asyncio.run(_create_bucket())


@cli.command()
@click.argument("bucket")
def delete_bucket(bucket):
    """Delete an S3 bucket."""

    async def _delete_bucket():
        client = get_client_from_env()

        async with client:
            await client.delete_bucket(bucket=bucket)

        click.echo("Bucket deleted successfully!")

    asyncio.run(_delete_bucket())


if __name__ == "__main__":
    cli()
