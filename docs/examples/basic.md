# Basic Usage Examples

This page demonstrates the core operations of the S3 Asyncio Client with practical, real-world scenarios.

## Setup and Authentication

```python
import asyncio
from s3_asyncio_client import S3Client

# Standard AWS S3 setup
async def create_client():
    client = S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key",
        region="us-east-1"
    )
    return client

# Using environment variables (recommended)
import os

async def create_client_from_env():
    client = S3Client(
        access_key=os.getenv("AWS_ACCESS_KEY_ID"),
        secret_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region=os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    )
    return client
```

## Using the Client as Context Manager

The recommended way to use the client is as an async context manager:

```python
async def main():
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key",
        region="us-east-1"
    ) as client:
        # All operations go here
        result = await client.list_objects("my-bucket")
        print(f"Found {len(result['objects'])} objects")
```

## Uploading Objects

### Simple Text Upload

```python
async def upload_text_file():
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    ) as client:
        
        # Upload a simple text file
        content = "Hello, S3! This is my first upload."
        result = await client.put_object(
            bucket="my-bucket",
            key="documents/hello.txt",
            data=content.encode("utf-8"),
            content_type="text/plain"
        )
        
        print(f"Uploaded successfully! ETag: {result['etag']}")
        return result

# Run the upload
asyncio.run(upload_text_file())
```

### Upload with Custom Metadata

```python
async def upload_with_metadata():
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    ) as client:
        
        # Read a local file
        with open("report.pdf", "rb") as f:
            file_data = f.read()
        
        # Upload with custom metadata
        result = await client.put_object(
            bucket="company-documents",
            key="reports/monthly-report.pdf",
            data=file_data,
            content_type="application/pdf",
            metadata={
                "author": "John Doe",
                "department": "Finance",
                "created-date": "2024-01-15",
                "version": "1.0"
            }
        )
        
        print(f"Report uploaded with ETag: {result['etag']}")
        return result
```

### Batch Upload with Error Handling

```python
from s3_asyncio_client.exceptions import S3Error, S3NotFoundError

async def batch_upload_files():
    files_to_upload = [
        ("images/photo1.jpg", "image/jpeg"),
        ("images/photo2.jpg", "image/jpeg"),
        ("documents/manual.pdf", "application/pdf"),
        ("data/results.csv", "text/csv")
    ]
    
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    ) as client:
        
        results = []
        for file_path, content_type in files_to_upload:
            try:
                with open(file_path, "rb") as f:
                    file_data = f.read()
                
                # Use the filename as the S3 key
                key = file_path.split("/")[-1]
                
                result = await client.put_object(
                    bucket="my-uploads",
                    key=f"batch-upload/{key}",
                    data=file_data,
                    content_type=content_type
                )
                
                results.append({
                    "file": file_path,
                    "key": f"batch-upload/{key}",
                    "success": True,
                    "etag": result["etag"]
                })
                print(f"✓ Uploaded {file_path}")
                
            except FileNotFoundError:
                print(f"✗ File not found: {file_path}")
                results.append({
                    "file": file_path,
                    "success": False,
                    "error": "File not found"
                })
            except S3Error as e:
                print(f"✗ S3 error uploading {file_path}: {e}")
                results.append({
                    "file": file_path,
                    "success": False,
                    "error": str(e)
                })
        
        return results
```

## Downloading Objects

### Simple Download

```python
async def download_file():
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    ) as client:
        
        try:
            result = await client.get_object(
                bucket="my-bucket",
                key="documents/hello.txt"
            )
            
            # Save to local file
            with open("downloaded_hello.txt", "wb") as f:
                f.write(result["body"])
            
            print(f"Downloaded file:")
            print(f"  Size: {result['content_length']} bytes")
            print(f"  Content-Type: {result['content_type']}")
            print(f"  Last Modified: {result['last_modified']}")
            print(f"  ETag: {result['etag']}")
            
            # Access custom metadata
            if result["metadata"]:
                print("  Custom metadata:")
                for key, value in result["metadata"].items():
                    print(f"    {key}: {value}")
            
        except S3NotFoundError:
            print("File not found in S3")
        except S3Error as e:
            print(f"Error downloading file: {e}")
```

### Download with Streaming

```python
async def download_large_file():
    """Download a large file efficiently."""
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    ) as client:
        
        try:
            result = await client.get_object(
                bucket="large-files",
                key="videos/presentation.mp4"
            )
            
            # Save directly to file
            with open("presentation.mp4", "wb") as f:
                f.write(result["body"])
            
            print(f"Downloaded {result['content_length']} bytes")
            
        except S3NotFoundError:
            print("Video file not found")
```

## Getting Object Metadata

```python
async def check_file_info():
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    ) as client:
        
        try:
            # Get metadata without downloading the file
            info = await client.head_object(
                bucket="my-bucket",
                key="large-dataset.zip"
            )
            
            print("File Information:")
            print(f"  Content-Type: {info['content_type']}")
            print(f"  Size: {info['content_length']:,} bytes")
            print(f"  Last Modified: {info['last_modified']}")
            print(f"  ETag: {info['etag']}")
            
            # Check if file is large enough to warrant multipart upload
            if info['content_length'] > 100 * 1024 * 1024:  # 100MB
                print("  Note: This file is large - consider multipart upload")
            
        except S3NotFoundError:
            print("File does not exist")
```

## Listing Objects

### Basic Listing

```python
async def list_bucket_contents():
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    ) as client:
        
        result = await client.list_objects(
            bucket="my-bucket",
            max_keys=10
        )
        
        print(f"Found {len(result['objects'])} objects:")
        for obj in result["objects"]:
            print(f"  {obj['key']} ({obj['size']:,} bytes)")
        
        if result["is_truncated"]:
            print(f"  ... and more (use continuation_token for next page)")
```

### Listing with Prefix Filter

```python
async def list_images():
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    ) as client:
        
        result = await client.list_objects(
            bucket="photo-storage",
            prefix="images/2024/",
            max_keys=50
        )
        
        print(f"Images from 2024:")
        total_size = 0
        for obj in result["objects"]:
            print(f"  {obj['key']} - {obj['size']:,} bytes")
            total_size += obj['size']
        
        print(f"Total: {len(result['objects'])} images, {total_size:,} bytes")
```

### Paginated Listing

```python
async def list_all_objects():
    """List all objects in a bucket using pagination."""
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    ) as client:
        
        all_objects = []
        continuation_token = None
        
        while True:
            result = await client.list_objects(
                bucket="large-bucket",
                max_keys=1000,
                continuation_token=continuation_token
            )
            
            all_objects.extend(result["objects"])
            print(f"Retrieved {len(result['objects'])} objects...")
            
            if not result["is_truncated"]:
                break
            
            continuation_token = result["next_continuation_token"]
        
        print(f"Total objects found: {len(all_objects)}")
        
        # Calculate total storage used
        total_size = sum(obj["size"] for obj in all_objects)
        print(f"Total storage: {total_size:,} bytes ({total_size / (1024**3):.2f} GB)")
        
        return all_objects
```

## Error Handling Best Practices

```python
from s3_asyncio_client.exceptions import (
    S3NotFoundError,
    S3AccessDeniedError,
    S3ClientError,
    S3ServerError
)

async def robust_s3_operation():
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    ) as client:
        
        try:
            # Attempt to get object info first
            info = await client.head_object(
                bucket="production-data",
                key="critical-file.json"
            )
            
            # If file exists, download it
            result = await client.get_object(
                bucket="production-data",
                key="critical-file.json"
            )
            
            return result["body"]
            
        except S3NotFoundError:
            print("File not found - this might be expected")
            return None
            
        except S3AccessDeniedError:
            print("Access denied - check your permissions")
            raise
            
        except S3ClientError as e:
            print(f"Client error (4xx): {e}")
            # Maybe retry with different parameters
            raise
            
        except S3ServerError as e:
            print(f"Server error (5xx): {e}")
            # Maybe implement retry logic
            raise
            
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise
```

## Working with Different Data Types

### JSON Data

```python
import json

async def work_with_json():
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    ) as client:
        
        # Upload JSON data
        data = {
            "user_id": 12345,
            "name": "John Doe",
            "settings": {
                "theme": "dark",
                "notifications": True
            }
        }
        
        json_str = json.dumps(data, indent=2)
        await client.put_object(
            bucket="user-data",
            key="users/12345/profile.json",
            data=json_str.encode("utf-8"),
            content_type="application/json"
        )
        
        # Download and parse JSON
        result = await client.get_object(
            bucket="user-data",
            key="users/12345/profile.json"
        )
        
        parsed_data = json.loads(result["body"].decode("utf-8"))
        print(f"User: {parsed_data['name']}")
```

### Binary Data

```python
async def work_with_images():
    from PIL import Image
    import io
    
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    ) as client:
        
        # Download image
        result = await client.get_object(
            bucket="images",
            key="photos/original.jpg"
        )
        
        # Process with PIL
        image = Image.open(io.BytesIO(result["body"]))
        
        # Create thumbnail
        image.thumbnail((200, 200))
        
        # Save thumbnail back to S3
        thumbnail_buffer = io.BytesIO()
        image.save(thumbnail_buffer, format="JPEG")
        thumbnail_data = thumbnail_buffer.getvalue()
        
        await client.put_object(
            bucket="images",
            key="photos/thumbnail.jpg",
            data=thumbnail_data,
            content_type="image/jpeg",
            metadata={
                "original-file": "photos/original.jpg",
                "thumbnail-size": "200x200"
            }
        )
```

## Complete Example: File Backup System

```python
import os
import asyncio
from pathlib import Path
from datetime import datetime

async def backup_directory():
    """Backup a local directory to S3."""
    local_dir = Path("./documents")
    bucket_name = "my-backups"
    backup_prefix = f"backups/{datetime.now().strftime('%Y-%m-%d')}"
    
    async with S3Client(
        access_key=os.getenv("AWS_ACCESS_KEY_ID"),
        secret_key=os.getenv("AWS_SECRET_ACCESS_KEY")
    ) as client:
        
        uploaded_files = []
        errors = []
        
        # Walk through all files in directory
        for file_path in local_dir.rglob("*"):
            if file_path.is_file():
                try:
                    # Read file
                    with open(file_path, "rb") as f:
                        file_data = f.read()
                    
                    # Create S3 key preserving directory structure
                    relative_path = file_path.relative_to(local_dir)
                    s3_key = f"{backup_prefix}/{relative_path}"
                    
                    # Determine content type
                    content_type = "application/octet-stream"
                    if file_path.suffix.lower() in [".txt", ".md"]:
                        content_type = "text/plain"
                    elif file_path.suffix.lower() in [".json"]:
                        content_type = "application/json"
                    elif file_path.suffix.lower() in [".pdf"]:
                        content_type = "application/pdf"
                    
                    # Upload file
                    result = await client.put_object(
                        bucket=bucket_name,
                        key=s3_key,
                        data=file_data,
                        content_type=content_type,
                        metadata={
                            "original-path": str(file_path),
                            "backup-date": datetime.now().isoformat(),
                            "file-size": str(len(file_data))
                        }
                    )
                    
                    uploaded_files.append({
                        "local_path": str(file_path),
                        "s3_key": s3_key,
                        "size": len(file_data),
                        "etag": result["etag"]
                    })
                    
                    print(f"✓ Backed up: {file_path}")
                    
                except Exception as e:
                    errors.append({
                        "file": str(file_path),
                        "error": str(e)
                    })
                    print(f"✗ Failed to backup: {file_path} - {e}")
        
        print(f"\nBackup Summary:")
        print(f"  Successfully backed up: {len(uploaded_files)} files")
        print(f"  Errors: {len(errors)} files")
        
        total_size = sum(f["size"] for f in uploaded_files)
        print(f"  Total data backed up: {total_size:,} bytes")
        
        return uploaded_files, errors

# Run the backup
if __name__ == "__main__":
    asyncio.run(backup_directory())
```