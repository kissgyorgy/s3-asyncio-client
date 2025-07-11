#!/usr/bin/env python3
import asyncio
import json
import os
import sys

import click

from .base import S3Client


@click.group()
@click.option("--config-file", help="Path to AWS config file")
@click.option("--profile", help="AWS profile name to use (default: 'default')")
@click.pass_context
def cli(ctx, config_file, profile):
    """Uploading/download files to/from any S3 provider."""
    ctx.ensure_object(dict)

    if config_file or profile:
        try:
            client = S3Client.from_aws_config(
                config_path=config_file, profile_name=profile or "default"
            )
        except (FileNotFoundError, ValueError) as e:
            click.echo(f"Error loading config file: {e}", err=True)
            sys.exit(1)
    else:
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        endpoint_url = os.getenv("AWS_ENDPOINT_URL")

        if not access_key or not secret_key:
            click.echo(
                "Error: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set",
                err=True,
            )
            sys.exit(1)

        client = S3Client(
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            endpoint_url=endpoint_url,
        )

    ctx.obj["client"] = client


@cli.command()
@click.argument("bucket")
@click.argument("key")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--content-type", help="Content type of the object")
@click.option("--metadata", help="JSON string of metadata key-value pairs")
@click.pass_context
def put_object(ctx, bucket, key, file_path, content_type, metadata):
    """Upload a local file to an S3 bucket."""

    async def _put():
        client = ctx.obj["client"]

        with open(file_path, "rb") as f:
            data = f.read()

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
@click.pass_context
def get_object(ctx, bucket, key, output_path):
    """Download an object from S3 to a local file."""

    async def _get():
        client = ctx.obj["client"]

        async with client:
            result = await client.get_object(bucket=bucket, key=key)

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
@click.pass_context
def head_object(ctx, bucket, key):
    """Get object metadata without downloading the object."""

    async def _head():
        client = ctx.obj["client"]

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
@click.pass_context
def list_objects(ctx, bucket, prefix, max_keys):
    """List all objects in a bucket without downloading them."""

    async def _list():
        client = ctx.obj["client"]

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
@click.pass_context
def presign_url(ctx, method, bucket, key, expires_in):
    """Create a pre-signed URL for a single operation later."""
    client = ctx.obj["client"]

    url = client.generate_presigned_url(
        method=method.upper(), bucket=bucket, key=key, expires_in=expires_in
    )

    click.echo(url)


@cli.command()
@click.argument("bucket")
@click.argument("key")
@click.pass_context
def delete_object(ctx, bucket, key):
    """Delete an object from an S3 bucket."""

    async def _delete():
        client = ctx.obj["client"]

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
@click.pass_context
def create_bucket(ctx, bucket):
    """Create a new S3 bucket."""

    async def _create_bucket():
        client = ctx.obj["client"]

        async with client:
            result = await client.create_bucket(bucket=bucket)

        click.echo("Bucket created successfully!")
        if result.get("location"):
            click.echo(f"Location: {result['location']}")

    asyncio.run(_create_bucket())


@cli.command()
@click.argument("bucket")
@click.pass_context
def delete_bucket(ctx, bucket):
    """Delete an existing S3 bucket."""

    async def _delete_bucket():
        client = ctx.obj["client"]

        async with client:
            await client.delete_bucket(bucket=bucket)

        click.echo("Bucket deleted successfully!")

    asyncio.run(_delete_bucket())


if __name__ == "__main__":
    cli()
