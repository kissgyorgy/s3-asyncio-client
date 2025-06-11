# Multipart Upload Examples

Multipart uploads are essential for uploading large files efficiently to S3. They allow you to upload files in parallel chunks, resume interrupted uploads, and handle files larger than 5GB.

## When to Use Multipart Upload

- Files larger than 100MB (recommended)
- Files larger than 5GB (required)
- Unreliable network connections
- When you want parallel upload performance
- When you need upload resumption capabilities

## Basic Multipart Upload

### Automatic Multipart Upload

The simplest way to use multipart upload is with the built-in `upload_file_multipart` method:

```python
import asyncio
from s3_asyncio_client import S3Client

async def upload_large_file():
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    ) as client:
        
        # Read a large file
        with open("large_video.mp4", "rb") as f:
            file_data = f.read()
        
        print(f"Uploading {len(file_data):,} bytes...")
        
        # Automatic multipart upload
        result = await client.upload_file_multipart(
            bucket="video-storage",
            key="uploads/large_video.mp4",
            data=file_data,
            part_size=10 * 1024 * 1024,  # 10MB parts
            content_type="video/mp4",
            metadata={
                "uploaded-by": "video-processor",
                "original-filename": "large_video.mp4"
            }
        )
        
        print(f"Upload complete!")
        print(f"  ETag: {result['etag']}")
        print(f"  Location: {result.get('location', 'N/A')}")
        
        return result

# Run the upload
asyncio.run(upload_large_file())
```

### Manual Multipart Upload Control

For more control over the upload process, you can manually manage multipart uploads:

```python
async def manual_multipart_upload():
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    ) as client:
        
        # Read the file
        with open("dataset.zip", "rb") as f:
            file_data = f.read()
        
        file_size = len(file_data)
        part_size = 10 * 1024 * 1024  # 10MB parts
        
        print(f"Starting multipart upload for {file_size:,} bytes")
        
        # Step 1: Initiate multipart upload
        multipart = await client.create_multipart_upload(
            bucket="data-storage",
            key="datasets/large_dataset.zip",
            content_type="application/zip",
            metadata={
                "source": "data-pipeline",
                "size": str(file_size)
            }
        )
        
        try:
            # Step 2: Upload parts
            part_number = 1
            offset = 0
            
            while offset < file_size:
                # Calculate part boundaries
                end_offset = min(offset + part_size, file_size)
                part_data = file_data[offset:end_offset]
                
                print(f"Uploading part {part_number} ({len(part_data):,} bytes)...")
                
                # Upload this part
                part_info = await multipart.upload_part(part_number, part_data)
                print(f"  Part {part_number} uploaded, ETag: {part_info['etag']}")
                
                # Move to next part
                offset = end_offset
                part_number += 1
            
            # Step 3: Complete the upload
            print("Completing multipart upload...")
            result = await multipart.complete()
            
            print(f"Upload completed successfully!")
            print(f"  ETag: {result['etag']}")
            print(f"  Parts: {result['parts_count']}")
            
            return result
            
        except Exception as e:
            # Step 4: Abort upload on error
            print(f"Error during upload: {e}")
            print("Aborting multipart upload...")
            await multipart.abort()
            raise
```

## Advanced Multipart Scenarios

### Upload with Progress Tracking

```python
import time

async def upload_with_progress():
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    ) as client:
        
        # Read file
        file_path = "large_backup.tar.gz"
        with open(file_path, "rb") as f:
            file_data = f.read()
        
        file_size = len(file_data)
        part_size = 8 * 1024 * 1024  # 8MB parts
        total_parts = (file_size + part_size - 1) // part_size
        
        print(f"Uploading {file_path} ({file_size:,} bytes) in {total_parts} parts")
        
        # Initialize multipart upload
        multipart = await client.create_multipart_upload(
            bucket="backups",
            key=f"archives/{file_path}",
            content_type="application/gzip"
        )
        
        start_time = time.time()
        uploaded_bytes = 0
        
        try:
            part_number = 1
            offset = 0
            
            while offset < file_size:
                part_start_time = time.time()
                
                # Get part data
                end_offset = min(offset + part_size, file_size)
                part_data = file_data[offset:end_offset]
                
                # Upload part
                await multipart.upload_part(part_number, part_data)
                
                # Update progress
                uploaded_bytes += len(part_data)
                elapsed_time = time.time() - start_time
                part_time = time.time() - part_start_time
                
                progress = (uploaded_bytes / file_size) * 100
                speed = uploaded_bytes / elapsed_time if elapsed_time > 0 else 0
                eta = (file_size - uploaded_bytes) / speed if speed > 0 else 0
                
                print(f"Part {part_number}/{total_parts} uploaded "
                      f"({progress:.1f}%, {speed/1024/1024:.1f} MB/s, "
                      f"ETA: {eta:.0f}s, Part time: {part_time:.1f}s)")
                
                offset = end_offset
                part_number += 1
            
            # Complete upload
            result = await multipart.complete()
            
            total_time = time.time() - start_time
            avg_speed = file_size / total_time / 1024 / 1024
            
            print(f"Upload completed in {total_time:.1f}s (avg: {avg_speed:.1f} MB/s)")
            return result
            
        except Exception as e:
            print(f"Upload failed: {e}")
            await multipart.abort()
            raise
```

### Parallel Part Upload

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def parallel_multipart_upload():
    """Upload parts in parallel for better performance."""
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    ) as client:
        
        # Read file
        with open("huge_file.bin", "rb") as f:
            file_data = f.read()
        
        file_size = len(file_data)
        part_size = 16 * 1024 * 1024  # 16MB parts for better parallelism
        
        print(f"Uploading {file_size:,} bytes with parallel parts")
        
        # Create multipart upload
        multipart = await client.create_multipart_upload(
            bucket="large-files",
            key="parallel_upload/huge_file.bin",
            content_type="application/octet-stream"
        )
        
        try:
            # Prepare all parts
            parts_to_upload = []
            part_number = 1
            offset = 0
            
            while offset < file_size:
                end_offset = min(offset + part_size, file_size)
                part_data = file_data[offset:end_offset]
                
                parts_to_upload.append({
                    'part_number': part_number,
                    'data': part_data,
                    'offset': offset
                })
                
                offset = end_offset
                part_number += 1
            
            print(f"Uploading {len(parts_to_upload)} parts in parallel...")
            
            # Upload parts concurrently (limit concurrency to avoid overwhelming S3)
            semaphore = asyncio.Semaphore(4)  # Max 4 concurrent uploads
            
            async def upload_single_part(part_info):
                async with semaphore:
                    print(f"Starting part {part_info['part_number']}")
                    result = await multipart.upload_part(
                        part_info['part_number'], 
                        part_info['data']
                    )
                    print(f"Completed part {part_info['part_number']}")
                    return result
            
            # Execute parallel uploads
            start_time = time.time()
            part_results = await asyncio.gather(
                *[upload_single_part(part) for part in parts_to_upload],
                return_exceptions=True
            )
            
            # Check for errors
            for i, result in enumerate(part_results):
                if isinstance(result, Exception):
                    print(f"Part {i+1} failed: {result}")
                    raise result
            
            upload_time = time.time() - start_time
            print(f"All parts uploaded in {upload_time:.1f}s")
            
            # Complete the upload
            result = await multipart.complete()
            
            total_time = time.time() - start_time
            speed = file_size / total_time / 1024 / 1024
            print(f"Parallel upload completed! Speed: {speed:.1f} MB/s")
            
            return result
            
        except Exception as e:
            print(f"Parallel upload failed: {e}")
            await multipart.abort()
            raise
```

### Resume Failed Upload

```python
import pickle
import os

async def resumable_upload():
    """Upload with ability to resume from interruption."""
    checkpoint_file = "upload_checkpoint.pkl"
    
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    ) as client:
        
        file_path = "critical_data.db"
        with open(file_path, "rb") as f:
            file_data = f.read()
        
        file_size = len(file_data)
        part_size = 10 * 1024 * 1024  # 10MB parts
        
        # Try to load previous checkpoint
        upload_state = None
        if os.path.exists(checkpoint_file):
            try:
                with open(checkpoint_file, "rb") as f:
                    upload_state = pickle.load(f)
                print(f"Resuming previous upload from part {len(upload_state['completed_parts']) + 1}")
            except Exception as e:
                print(f"Could not load checkpoint: {e}")
                upload_state = None
        
        if upload_state is None:
            # Start new upload
            print("Starting new resumable upload...")
            multipart = await client.create_multipart_upload(
                bucket="critical-data",
                key="backups/critical_data.db",
                content_type="application/octet-stream"
            )
            
            upload_state = {
                'bucket': "critical-data",
                'key': "backups/critical_data.db",
                'upload_id': multipart.upload_id,
                'file_size': file_size,
                'part_size': part_size,
                'completed_parts': []
            }
        else:
            # Resume existing upload
            multipart = MultipartUpload(
                client, 
                upload_state['bucket'], 
                upload_state['key'], 
                upload_state['upload_id']
            )
            # Restore completed parts
            multipart.parts = upload_state['completed_parts']
        
        try:
            # Calculate which parts still need uploading
            completed_part_numbers = {p['part_number'] for p in upload_state['completed_parts']}
            total_parts = (file_size + part_size - 1) // part_size
            
            for part_number in range(1, total_parts + 1):
                if part_number in completed_part_numbers:
                    print(f"Part {part_number} already uploaded, skipping")
                    continue
                
                # Calculate part boundaries
                offset = (part_number - 1) * part_size
                end_offset = min(offset + part_size, file_size)
                part_data = file_data[offset:end_offset]
                
                print(f"Uploading part {part_number}/{total_parts} ({len(part_data):,} bytes)")
                
                # Upload part
                part_info = await multipart.upload_part(part_number, part_data)
                upload_state['completed_parts'].append(part_info)
                
                # Save checkpoint
                with open(checkpoint_file, "wb") as f:
                    pickle.dump(upload_state, f)
                
                print(f"Part {part_number} completed and checkpointed")
            
            # Complete upload
            print("Completing upload...")
            result = await multipart.complete()
            
            # Clean up checkpoint
            os.remove(checkpoint_file)
            print("Upload completed and checkpoint cleaned up")
            
            return result
            
        except Exception as e:
            print(f"Upload interrupted: {e}")
            print(f"Progress saved to {checkpoint_file}")
            raise
```

### Memory-Efficient Large File Upload

```python
async def memory_efficient_upload():
    """Upload very large files without loading entire file into memory."""
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    ) as client:
        
        file_path = "enormous_file.bin"
        part_size = 50 * 1024 * 1024  # 50MB parts
        
        # Get file size without loading into memory
        file_size = os.path.getsize(file_path)
        total_parts = (file_size + part_size - 1) // part_size
        
        print(f"Uploading {file_path} ({file_size:,} bytes) in {total_parts} parts")
        
        # Create multipart upload
        multipart = await client.create_multipart_upload(
            bucket="enormous-files",
            key=f"uploads/{os.path.basename(file_path)}",
            content_type="application/octet-stream",
            metadata={
                "source-file": file_path,
                "upload-method": "memory-efficient"
            }
        )
        
        try:
            part_number = 1
            
            with open(file_path, "rb") as f:
                while True:
                    # Read one part at a time
                    part_data = f.read(part_size)
                    if not part_data:
                        break
                    
                    print(f"Uploading part {part_number}/{total_parts} "
                          f"({len(part_data):,} bytes)")
                    
                    # Upload this part
                    await multipart.upload_part(part_number, part_data)
                    
                    part_number += 1
                    
                    # Memory cleanup (though Python should handle this)
                    del part_data
            
            # Complete upload
            result = await multipart.complete()
            print(f"Memory-efficient upload completed!")
            
            return result
            
        except Exception as e:
            print(f"Upload failed: {e}")
            await multipart.abort()
            raise
```

## Error Handling and Retry Logic

```python
import asyncio
from s3_asyncio_client.exceptions import S3Error, S3ServerError

async def robust_multipart_upload():
    """Multipart upload with comprehensive error handling."""
    max_retries = 3
    retry_delay = 2  # seconds
    
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    ) as client:
        
        with open("important_file.zip", "rb") as f:
            file_data = f.read()
        
        multipart = None
        
        try:
            # Create multipart upload
            multipart = await client.create_multipart_upload(
                bucket="important-files",
                key="uploads/important_file.zip",
                content_type="application/zip"
            )
            
            file_size = len(file_data)
            part_size = 10 * 1024 * 1024
            part_number = 1
            offset = 0
            failed_parts = []
            
            # Upload all parts with retry logic
            while offset < file_size:
                end_offset = min(offset + part_size, file_size)
                part_data = file_data[offset:end_offset]
                
                # Retry logic for each part
                for attempt in range(max_retries + 1):
                    try:
                        print(f"Uploading part {part_number} (attempt {attempt + 1})")
                        await multipart.upload_part(part_number, part_data)
                        print(f"Part {part_number} uploaded successfully")
                        break
                        
                    except S3ServerError as e:
                        if attempt < max_retries:
                            print(f"Server error on part {part_number}, retrying in {retry_delay}s: {e}")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            print(f"Part {part_number} failed after {max_retries} retries")
                            failed_parts.append(part_number)
                            raise
                    
                    except S3Error as e:
                        print(f"Non-retryable error on part {part_number}: {e}")
                        failed_parts.append(part_number)
                        raise
                
                offset = end_offset
                part_number += 1
            
            if failed_parts:
                raise Exception(f"Failed to upload parts: {failed_parts}")
            
            # Complete upload
            result = await multipart.complete()
            print("Robust upload completed successfully!")
            return result
            
        except Exception as e:
            print(f"Upload failed: {e}")
            if multipart:
                try:
                    print("Aborting multipart upload...")
                    await multipart.abort()
                    print("Multipart upload aborted")
                except Exception as abort_error:
                    print(f"Error aborting upload: {abort_error}")
            raise
```

## Performance Optimization Tips

### Optimal Part Sizes

```python
def calculate_optimal_part_size(file_size_bytes):
    """Calculate optimal part size based on file size."""
    # S3 limits: 5MB minimum part size, 5GB maximum part size, 10,000 parts max
    
    min_part_size = 5 * 1024 * 1024      # 5MB
    max_part_size = 5 * 1024 * 1024 * 1024  # 5GB
    max_parts = 10000
    
    # Calculate ideal part size to use close to max_parts for best parallelism
    ideal_part_size = file_size_bytes // max_parts
    
    # Ensure within bounds
    if ideal_part_size < min_part_size:
        return min_part_size
    elif ideal_part_size > max_part_size:
        return max_part_size
    else:
        # Round up to nearest MB for cleaner parts
        return ((ideal_part_size // (1024 * 1024)) + 1) * (1024 * 1024)

async def optimized_upload():
    file_path = "massive_dataset.tar.gz"
    file_size = os.path.getsize(file_path)
    optimal_part_size = calculate_optimal_part_size(file_size)
    
    print(f"File size: {file_size:,} bytes")
    print(f"Optimal part size: {optimal_part_size:,} bytes ({optimal_part_size // 1024 // 1024} MB)")
    print(f"Estimated parts: {(file_size + optimal_part_size - 1) // optimal_part_size}")
    
    async with S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    ) as client:
        
        # Use optimal part size
        result = await client.upload_file_multipart(
            bucket="optimized-uploads",
            key="datasets/massive_dataset.tar.gz",
            data=open(file_path, "rb").read(),
            part_size=optimal_part_size,
            content_type="application/gzip"
        )
        
        return result
```

## Complete Example: Batch File Processor

```python
import asyncio
import os
from pathlib import Path
import mimetypes

async def batch_multipart_processor():
    """Process multiple large files with multipart uploads."""
    
    # Directory containing large files to upload
    source_dir = Path("./large_files")
    bucket_name = "batch-processed"
    
    # Size threshold for multipart upload (100MB)
    multipart_threshold = 100 * 1024 * 1024
    
    async with S3Client(
        access_key=os.getenv("AWS_ACCESS_KEY_ID"),
        secret_key=os.getenv("AWS_SECRET_ACCESS_KEY")
    ) as client:
        
        # Find all files to process
        files_to_process = []
        for file_path in source_dir.rglob("*"):
            if file_path.is_file():
                file_size = file_path.stat().st_size
                files_to_process.append({
                    'path': file_path,
                    'size': file_size,
                    'use_multipart': file_size > multipart_threshold
                })
        
        print(f"Found {len(files_to_process)} files to process")
        
        # Process files
        results = []
        for file_info in files_to_process:
            file_path = file_info['path']
            file_size = file_info['size']
            
            try:
                # Read file
                with open(file_path, "rb") as f:
                    file_data = f.read()
                
                # Determine content type
                content_type, _ = mimetypes.guess_type(str(file_path))
                if not content_type:
                    content_type = "application/octet-stream"
                
                # Create S3 key
                relative_path = file_path.relative_to(source_dir)
                s3_key = f"processed/{relative_path}"
                
                print(f"Processing {file_path} ({file_size:,} bytes)")
                
                if file_info['use_multipart']:
                    # Use multipart upload for large files
                    print(f"  Using multipart upload...")
                    result = await client.upload_file_multipart(
                        bucket=bucket_name,
                        key=s3_key,
                        data=file_data,
                        content_type=content_type,
                        metadata={
                            'original-path': str(file_path),
                            'processing-method': 'multipart',
                            'file-size': str(file_size)
                        }
                    )
                else:
                    # Use regular upload for smaller files
                    print(f"  Using regular upload...")
                    result = await client.put_object(
                        bucket=bucket_name,
                        key=s3_key,
                        data=file_data,
                        content_type=content_type,
                        metadata={
                            'original-path': str(file_path),
                            'processing-method': 'regular',
                            'file-size': str(file_size)
                        }
                    )
                
                results.append({
                    'file': str(file_path),
                    'key': s3_key,
                    'size': file_size,
                    'method': 'multipart' if file_info['use_multipart'] else 'regular',
                    'success': True,
                    'etag': result['etag']
                })
                
                print(f"  ✓ Completed: {s3_key}")
                
            except Exception as e:
                print(f"  ✗ Failed: {file_path} - {e}")
                results.append({
                    'file': str(file_path),
                    'success': False,
                    'error': str(e)
                })
        
        # Summary
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        total_size = sum(r.get('size', 0) for r in results if r['success'])
        
        print(f"\nBatch Processing Summary:")
        print(f"  Total files: {len(results)}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"  Total data processed: {total_size:,} bytes ({total_size / 1024**3:.2f} GB)")
        
        return results

# Run the batch processor
if __name__ == "__main__":
    asyncio.run(batch_multipart_processor())
```