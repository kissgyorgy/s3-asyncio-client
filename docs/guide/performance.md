# Performance Tips

This guide covers performance optimization strategies, concurrent operations, connection management, memory efficiency, and best practices for the S3 Asyncio Client.

## Connection Management

### Connection Pooling

The client uses aiohttp's connection pooling by default, but you can optimize it for your specific use case:

```python
import aiohttp
from s3_asyncio_client import S3Client

# Custom connection pooling configuration
connector = aiohttp.TCPConnector(
    limit=100,              # Total connection pool size
    limit_per_host=30,      # Max connections per host
    ttl_dns_cache=300,      # DNS cache TTL (5 minutes)
    use_dns_cache=True,     # Enable DNS caching
    enable_cleanup_closed=True,  # Clean up closed connections
    keepalive_timeout=30,   # Keep-alive timeout
    force_close=False,      # Don't force close connections
)

# Custom timeout configuration
timeout = aiohttp.ClientTimeout(
    total=300,      # Total timeout (5 minutes)
    connect=10,     # Connection timeout
    sock_read=60,   # Socket read timeout
)

async with aiohttp.ClientSession(
    connector=connector,
    timeout=timeout
) as session:
    client = S3Client(access_key, secret_key, region)
    client._session = session
    
    # Perform operations with optimized connection pooling
    tasks = []
    for i in range(100):
        task = client.put_object("bucket", f"file-{i}.txt", f"content-{i}".encode())
        tasks.append(task)
    
    # Execute concurrently with optimized connections
    results = await asyncio.gather(*tasks)
    print(f"Uploaded {len(results)} files")
```

### Session Reuse

Always reuse the client session for multiple operations:

```python
# Good: Reuse client session
async with S3Client(access_key, secret_key, region) as client:
    # Perform multiple operations
    await client.put_object("bucket", "file1.txt", b"content1")
    await client.put_object("bucket", "file2.txt", b"content2")
    await client.get_object("bucket", "file1.txt")
    await client.list_objects("bucket")

# Avoid: Creating new client for each operation
# This creates unnecessary session overhead
for i in range(10):
    async with S3Client(access_key, secret_key, region) as client:
        await client.put_object("bucket", f"file-{i}.txt", f"content-{i}".encode())
```

### Keep-Alive Optimization

Configure keep-alive settings for long-running applications:

```python
# Optimized connector for long-running applications
connector = aiohttp.TCPConnector(
    limit=50,                    # Reasonable pool size
    limit_per_host=20,           # Max per S3 endpoint
    keepalive_timeout=60,        # Longer keep-alive
    enable_cleanup_closed=True,   # Clean up closed connections
    ttl_dns_cache=600,           # 10-minute DNS cache
)

class OptimizedS3Client:
    def __init__(self, access_key, secret_key, region):
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self._client = None
        self._session = None
    
    async def __aenter__(self):
        self._session = aiohttp.ClientSession(connector=connector)
        self._client = S3Client(self.access_key, self.secret_key, self.region)
        self._client._session = self._session
        return self._client
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()

# Usage for long-running applications
async with OptimizedS3Client(access_key, secret_key, region) as client:
    # Perform many operations efficiently
    for batch in range(10):
        tasks = []
        for i in range(20):
            task = client.put_object("bucket", f"batch-{batch}-file-{i}.txt", b"content")
            tasks.append(task)
        await asyncio.gather(*tasks)
```

## Concurrent Operations

### Controlled Concurrency

Use semaphores to limit concurrent operations and prevent overwhelming the server:

```python
import asyncio

async def concurrent_uploads_with_limit(client, bucket, files, max_concurrent=10):
    """Upload files with controlled concurrency."""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def upload_with_limit(key, data):
        async with semaphore:
            return await client.put_object(bucket, key, data)
    
    tasks = [upload_with_limit(key, data) for key, data in files]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    successful = [r for r in results if not isinstance(r, Exception)]
    failed = [r for r in results if isinstance(r, Exception)]
    
    return {
        "successful": len(successful),
        "failed": len(failed),
        "results": results
    }

# Usage
files_to_upload = [(f"file-{i}.txt", f"content-{i}".encode()) for i in range(100)]

async with S3Client(access_key, secret_key, region) as client:
    result = await concurrent_uploads_with_limit(
        client, "my-bucket", files_to_upload, max_concurrent=15
    )
    print(f"Uploaded: {result['successful']}, Failed: {result['failed']}")
```

### Batched Operations

Process operations in batches to balance performance and resource usage:

```python
async def batched_operations(client, operations, batch_size=20, delay_between_batches=0.1):
    """Execute operations in batches with delays."""
    results = []
    
    for i in range(0, len(operations), batch_size):
        batch = operations[i:i + batch_size]
        
        # Execute batch concurrently
        batch_tasks = [op() for op in batch]
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        results.extend(batch_results)
        
        # Small delay between batches to avoid rate limiting
        if i + batch_size < len(operations):
            await asyncio.sleep(delay_between_batches)
        
        print(f"Completed batch {i // batch_size + 1}/{(len(operations) + batch_size - 1) // batch_size}")
    
    return results

# Usage
operations = [
    lambda: client.put_object("bucket", f"file-{i}.txt", f"content-{i}".encode())
    for i in range(200)
]

async with S3Client(access_key, secret_key, region) as client:
    results = await batched_operations(client, operations, batch_size=25)
```

### Producer-Consumer Pattern

Use producer-consumer pattern for streaming operations:

```python
import asyncio
from asyncio import Queue

async def producer_consumer_upload(client, bucket, data_generator, max_workers=5, queue_size=50):
    """Upload using producer-consumer pattern."""
    upload_queue = Queue(maxsize=queue_size)
    results_queue = Queue()
    
    # Producer: Generate upload tasks
    async def producer():
        async for key, data in data_generator:
            await upload_queue.put((key, data))
        
        # Signal completion
        for _ in range(max_workers):
            await upload_queue.put(None)
    
    # Consumer: Process uploads
    async def consumer(worker_id):
        while True:
            item = await upload_queue.get()
            if item is None:
                break
            
            key, data = item
            try:
                result = await client.put_object(bucket, key, data)
                await results_queue.put({"key": key, "success": True, "result": result})
            except Exception as e:
                await results_queue.put({"key": key, "success": False, "error": str(e)})
            finally:
                upload_queue.task_done()
    
    # Start producer and consumers
    producer_task = asyncio.create_task(producer())
    consumer_tasks = [
        asyncio.create_task(consumer(i)) for i in range(max_workers)
    ]
    
    # Collect results
    results = []
    completed_workers = 0
    
    while completed_workers < max_workers:
        try:
            result = await asyncio.wait_for(results_queue.get(), timeout=1.0)
            results.append(result)
        except asyncio.TimeoutError:
            # Check if all workers are done
            if all(task.done() for task in consumer_tasks):
                break
    
    # Wait for completion
    await producer_task
    await asyncio.gather(*consumer_tasks)
    
    return results

# Example data generator
async def generate_upload_data():
    """Generate data for uploads."""
    for i in range(100):
        key = f"generated-file-{i}.txt"
        data = f"Generated content {i} at {time.time()}".encode()
        yield key, data
        await asyncio.sleep(0.01)  # Simulate data generation delay

# Usage
async with S3Client(access_key, secret_key, region) as client:
    results = await producer_consumer_upload(
        client, "my-bucket", generate_upload_data(), max_workers=8
    )
    successful = [r for r in results if r["success"]]
    print(f"Uploaded {len(successful)} files")
```

## Memory Management

### Streaming Large Files

Handle large files without loading them entirely into memory:

```python
async def stream_upload_large_file(client, bucket, key, file_path, chunk_size=8192):
    """Upload large file in chunks to minimize memory usage."""
    file_size = os.path.getsize(file_path)
    
    # Use multipart upload for large files
    if file_size > 5 * 1024 * 1024:  # 5MB threshold
        return await stream_multipart_upload(client, bucket, key, file_path)
    
    # For smaller files, stream into memory in chunks
    chunks = []
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            chunks.append(chunk)
    
    data = b''.join(chunks)
    return await client.put_object(bucket, key, data)

async def stream_multipart_upload(client, bucket, key, file_path, part_size=5*1024*1024):
    """Stream multipart upload to minimize memory usage."""
    multipart = await client.create_multipart_upload(bucket, key)
    
    try:
        part_number = 1
        
        with open(file_path, "rb") as f:
            while True:
                # Read one part at a time
                part_data = f.read(part_size)
                if not part_data:
                    break
                
                # Upload part immediately
                await multipart.upload_part(part_number, part_data)
                part_number += 1
                
                # Part data is automatically garbage collected
        
        return await multipart.complete()
        
    except Exception:
        await multipart.abort()
        raise

# Memory-efficient download
async def stream_download_large_file(client, bucket, key, output_path, chunk_size=8192):
    """Download large file in chunks to minimize memory usage."""
    response = await client._make_request("GET", bucket, key)
    
    with open(output_path, "wb") as f:
        async for chunk in response.content.iter_chunked(chunk_size):
            f.write(chunk)
    
    return {"downloaded": True, "path": output_path}

# Usage
async with S3Client(access_key, secret_key, region) as client:
    # Upload large file efficiently
    await stream_upload_large_file(client, "bucket", "large-file.bin", "/path/to/large-file.bin")
    
    # Download large file efficiently
    await stream_download_large_file(client, "bucket", "large-file.bin", "/path/to/downloaded-file.bin")
```

### Memory Pool for Repeated Operations

Use memory pooling for repeated operations with similar data sizes:

```python
from collections import deque
import weakref

class MemoryPool:
    """Simple memory pool for reusing byte arrays."""
    
    def __init__(self, pool_size=10):
        self.pools = {}  # size -> deque of buffers
        self.pool_size = pool_size
    
    def get_buffer(self, size):
        """Get a buffer of the specified size."""
        # Round up to nearest power of 2 for better reuse
        rounded_size = 1 << (size - 1).bit_length()
        
        if rounded_size not in self.pools:
            self.pools[rounded_size] = deque()
        
        pool = self.pools[rounded_size]
        
        if pool:
            return pool.popleft()
        else:
            return bytearray(rounded_size)
    
    def return_buffer(self, buffer):
        """Return a buffer to the pool."""
        size = len(buffer)
        
        if size not in self.pools:
            self.pools[size] = deque()
        
        pool = self.pools[size]
        
        if len(pool) < self.pool_size:
            # Clear buffer content and return to pool
            buffer[:] = b'\x00' * len(buffer)
            pool.append(buffer)

# Usage with memory pool
memory_pool = MemoryPool(pool_size=5)

async def efficient_batch_upload(client, bucket, files_data):
    """Upload files using memory pool."""
    results = []
    
    for key, content in files_data:
        # Get buffer from pool
        content_bytes = content.encode() if isinstance(content, str) else content
        buffer = memory_pool.get_buffer(len(content_bytes))
        
        try:
            # Copy content to buffer
            buffer[:len(content_bytes)] = content_bytes
            
            # Upload using buffer slice
            result = await client.put_object(bucket, key, bytes(buffer[:len(content_bytes)]))
            results.append(result)
            
        finally:
            # Return buffer to pool
            memory_pool.return_buffer(buffer)
    
    return results
```

### Garbage Collection Optimization

Optimize garbage collection for high-throughput operations:

```python
import gc
import time

async def gc_optimized_operations(client, operations, gc_threshold=100):
    """Execute operations with manual garbage collection optimization."""
    results = []
    operations_since_gc = 0
    
    # Disable automatic garbage collection temporarily
    gc.disable()
    
    try:
        for i, operation in enumerate(operations):
            result = await operation()
            results.append(result)
            operations_since_gc += 1
            
            # Manual garbage collection at intervals
            if operations_since_gc >= gc_threshold:
                gc.collect()
                operations_since_gc = 0
                
                # Optional: yield control to event loop
                await asyncio.sleep(0)
        
        # Final garbage collection
        gc.collect()
        
    finally:
        # Re-enable automatic garbage collection
        gc.enable()
    
    return results

# Usage
operations = [
    lambda: client.put_object("bucket", f"gc-test-{i}.txt", f"content-{i}".encode())
    for i in range(1000)
]

async with S3Client(access_key, secret_key, region) as client:
    start_time = time.time()
    results = await gc_optimized_operations(client, operations)
    duration = time.time() - start_time
    print(f"Completed {len(results)} operations in {duration:.2f}s")
```

## Multipart Upload Optimization

### Concurrent Part Uploads

Optimize multipart uploads with concurrent part uploads:

```python
async def optimized_multipart_upload(
    client, bucket, key, data, 
    part_size=8*1024*1024,      # 8MB parts for better performance
    max_concurrent_parts=5       # Limit concurrent uploads
):
    """Optimized multipart upload with concurrent parts."""
    if len(data) <= part_size:
        return await client.put_object(bucket, key, data)
    
    multipart = await client.create_multipart_upload(bucket, key)
    semaphore = asyncio.Semaphore(max_concurrent_parts)
    
    async def upload_part_with_limit(part_number, part_data):
        async with semaphore:
            return await multipart.upload_part(part_number, part_data)
    
    try:
        # Create part upload tasks
        tasks = []
        part_number = 1
        offset = 0
        
        while offset < len(data):
            end_offset = min(offset + part_size, len(data))
            part_data = data[offset:end_offset]
            
            task = upload_part_with_limit(part_number, part_data)
            tasks.append(task)
            
            offset = end_offset
            part_number += 1
        
        # Execute parts concurrently
        part_results = await asyncio.gather(*tasks)
        
        # Complete upload
        return await multipart.complete()
        
    except Exception:
        await multipart.abort()
        raise

# Usage
large_data = b"x" * (50 * 1024 * 1024)  # 50MB test data

async with S3Client(access_key, secret_key, region) as client:
    result = await optimized_multipart_upload(
        client, "bucket", "large-optimized.bin", large_data
    )
    print(f"Upload completed: {result['etag']}")
```

### Dynamic Part Sizing

Adjust part sizes based on file size for optimal performance:

```python
def calculate_optimal_part_size(file_size):
    """Calculate optimal part size based on file size."""
    min_part_size = 5 * 1024 * 1024    # 5MB minimum
    max_part_size = 100 * 1024 * 1024  # 100MB maximum
    max_parts = 10000                  # S3 limit
    
    # Calculate part size to stay under part limit
    calculated_size = file_size // max_parts
    
    # Ensure part size is within valid range
    part_size = max(min_part_size, min(calculated_size, max_part_size))
    
    # Round to nearest MB for consistency
    part_size = ((part_size + 1024*1024 - 1) // (1024*1024)) * 1024*1024
    
    return part_size

async def adaptive_multipart_upload(client, bucket, key, file_path):
    """Multipart upload with adaptive part sizing."""
    file_size = os.path.getsize(file_path)
    part_size = calculate_optimal_part_size(file_size)
    
    print(f"File size: {file_size // (1024*1024)}MB, Part size: {part_size // (1024*1024)}MB")
    
    multipart = await client.create_multipart_upload(bucket, key)
    
    try:
        part_number = 1
        
        with open(file_path, "rb") as f:
            while True:
                part_data = f.read(part_size)
                if not part_data:
                    break
                
                await multipart.upload_part(part_number, part_data)
                print(f"Uploaded part {part_number}")
                part_number += 1
        
        return await multipart.complete()
        
    except Exception:
        await multipart.abort()
        raise

# Usage
async with S3Client(access_key, secret_key, region) as client:
    result = await adaptive_multipart_upload(client, "bucket", "adaptive-upload.bin", "/path/to/large-file")
```

## Caching Strategies

### Response Caching

Implement caching for frequently accessed objects:

```python
import hashlib
import json
from datetime import datetime, timedelta

class S3Cache:
    """Simple in-memory cache for S3 responses."""
    
    def __init__(self, max_size=100, ttl_seconds=300):
        self.cache = {}
        self.access_times = {}
        self.max_size = max_size
        self.ttl = timedelta(seconds=ttl_seconds)
    
    def _make_key(self, bucket, key, operation):
        """Create cache key."""
        return f"{operation}:{bucket}:{key}"
    
    def _is_expired(self, timestamp):
        """Check if cache entry is expired."""
        return datetime.now() - timestamp > self.ttl
    
    def get(self, bucket, key, operation):
        """Get cached response."""
        cache_key = self._make_key(bucket, key, operation)
        
        if cache_key in self.cache:
            timestamp, data = self.cache[cache_key]
            
            if not self._is_expired(timestamp):
                self.access_times[cache_key] = datetime.now()
                return data
            else:
                # Remove expired entry
                del self.cache[cache_key]
                del self.access_times[cache_key]
        
        return None
    
    def put(self, bucket, key, operation, data):
        """Cache response."""
        cache_key = self._make_key(bucket, key, operation)
        
        # Evict least recently used if cache is full
        if len(self.cache) >= self.max_size:
            lru_key = min(self.access_times, key=self.access_times.get)
            del self.cache[lru_key]
            del self.access_times[lru_key]
        
        self.cache[cache_key] = (datetime.now(), data)
        self.access_times[cache_key] = datetime.now()

class CachedS3Client:
    """S3 client with response caching."""
    
    def __init__(self, client, cache=None):
        self.client = client
        self.cache = cache or S3Cache()
    
    async def get_object_cached(self, bucket, key):
        """Get object with caching."""
        # Check cache first
        cached = self.cache.get(bucket, key, "get_object")
        if cached:
            return cached
        
        # Fetch from S3
        response = await self.client.get_object(bucket, key)
        
        # Cache response (excluding body for memory efficiency)
        cacheable_response = response.copy()
        cacheable_response.pop("body", None)  # Don't cache large bodies
        
        self.cache.put(bucket, key, "get_object", cacheable_response)
        return response
    
    async def head_object_cached(self, bucket, key):
        """Head object with caching."""
        cached = self.cache.get(bucket, key, "head_object")
        if cached:
            return cached
        
        response = await self.client.head_object(bucket, key)
        self.cache.put(bucket, key, "head_object", response)
        return response

# Usage
async with S3Client(access_key, secret_key, region) as client:
    cached_client = CachedS3Client(client, S3Cache(max_size=50, ttl_seconds=600))
    
    # First call hits S3
    metadata1 = await cached_client.head_object_cached("bucket", "file.txt")
    
    # Second call uses cache
    metadata2 = await cached_client.head_object_cached("bucket", "file.txt")
```

### Metadata Caching

Cache object metadata for list operations:

```python
class MetadataCache:
    """Cache for object metadata from list operations."""
    
    def __init__(self, ttl_seconds=300):
        self.metadata_cache = {}
        self.list_cache = {}
        self.ttl = timedelta(seconds=ttl_seconds)
    
    def cache_list_response(self, bucket, prefix, response):
        """Cache list response and individual object metadata."""
        timestamp = datetime.now()
        
        # Cache the list response
        list_key = f"{bucket}:{prefix or ''}"
        self.list_cache[list_key] = (timestamp, response)
        
        # Cache individual object metadata
        for obj in response.get("objects", []):
            obj_key = f"{bucket}:{obj['key']}"
            metadata = {
                "content_length": obj["size"],
                "last_modified": obj["last_modified"],
                "etag": obj["etag"],
                "storage_class": obj.get("storage_class", "STANDARD")
            }
            self.metadata_cache[obj_key] = (timestamp, metadata)
    
    def get_object_metadata(self, bucket, key):
        """Get cached object metadata."""
        cache_key = f"{bucket}:{key}"
        
        if cache_key in self.metadata_cache:
            timestamp, metadata = self.metadata_cache[cache_key]
            if datetime.now() - timestamp <= self.ttl:
                return metadata
        
        return None

# Enhanced client with metadata caching
class MetadataCachedS3Client:
    def __init__(self, client):
        self.client = client
        self.metadata_cache = MetadataCache()
    
    async def list_objects_with_cache(self, bucket, prefix=None):
        """List objects and cache metadata."""
        response = await self.client.list_objects(bucket, prefix=prefix)
        self.metadata_cache.cache_list_response(bucket, prefix, response)
        return response
    
    async def head_object_fast(self, bucket, key):
        """Fast head object using cached metadata."""
        cached = self.metadata_cache.get_object_metadata(bucket, key)
        if cached:
            return cached
        
        # Fall back to actual head request
        return await self.client.head_object(bucket, key)
```

## Performance Monitoring

### Operation Timing

Monitor operation performance:

```python
import time
from collections import defaultdict

class PerformanceMonitor:
    """Monitor S3 operation performance."""
    
    def __init__(self):
        self.timings = defaultdict(list)
        self.operation_counts = defaultdict(int)
    
    async def timed_operation(self, operation_name, operation_func):
        """Execute operation with timing."""
        start_time = time.perf_counter()
        try:
            result = await operation_func()
            success = True
        except Exception as e:
            result = e
            success = False
        finally:
            duration = time.perf_counter() - start_time
            
            self.timings[operation_name].append(duration)
            self.operation_counts[operation_name] += 1
            
            if not success:
                self.operation_counts[f"{operation_name}_failed"] += 1
        
        if not success:
            raise result
        return result
    
    def get_stats(self):
        """Get performance statistics."""
        stats = {}
        
        for operation, times in self.timings.items():
            if times:
                stats[operation] = {
                    "count": len(times),
                    "total_time": sum(times),
                    "avg_time": sum(times) / len(times),
                    "min_time": min(times),
                    "max_time": max(times),
                    "failed_count": self.operation_counts.get(f"{operation}_failed", 0)
                }
        
        return stats

# Usage
monitor = PerformanceMonitor()

async def monitored_s3_operations(client):
    """Example operations with monitoring."""
    
    # Upload with monitoring
    await monitor.timed_operation(
        "put_object",
        lambda: client.put_object("bucket", "monitored-file.txt", b"test content")
    )
    
    # Download with monitoring
    await monitor.timed_operation(
        "get_object",
        lambda: client.get_object("bucket", "monitored-file.txt")
    )
    
    # List with monitoring
    await monitor.timed_operation(
        "list_objects",
        lambda: client.list_objects("bucket")
    )

# Run operations and get stats
async with S3Client(access_key, secret_key, region) as client:
    await monitored_s3_operations(client)
    
    stats = monitor.get_stats()
    for operation, metrics in stats.items():
        print(f"{operation}: {metrics['avg_time']:.3f}s avg, {metrics['count']} ops")
```

### Throughput Measurement

Measure upload/download throughput:

```python
async def measure_throughput(client, operation_func, data_size, operation_name):
    """Measure operation throughput."""
    start_time = time.perf_counter()
    
    result = await operation_func()
    
    end_time = time.perf_counter()
    duration = end_time - start_time
    
    throughput_mbps = (data_size / (1024 * 1024)) / duration
    
    print(f"{operation_name}:")
    print(f"  Duration: {duration:.2f}s")
    print(f"  Throughput: {throughput_mbps:.2f} MB/s")
    
    return result, throughput_mbps

# Usage
test_data = b"x" * (10 * 1024 * 1024)  # 10MB test data

async with S3Client(access_key, secret_key, region) as client:
    # Measure upload throughput
    upload_result, upload_mbps = await measure_throughput(
        client,
        lambda: client.put_object("bucket", "throughput-test.bin", test_data),
        len(test_data),
        "Upload"
    )
    
    # Measure download throughput
    download_result, download_mbps = await measure_throughput(
        client,
        lambda: client.get_object("bucket", "throughput-test.bin"),
        len(test_data),
        "Download"
    )
```

## Best Practices Summary

### 1. Connection Management
- Use connection pooling with appropriate limits
- Reuse client sessions across operations
- Configure reasonable timeouts
- Enable keep-alive for long-running applications

### 2. Concurrency Control
- Limit concurrent operations with semaphores
- Use batching for large numbers of operations
- Implement backoff strategies for rate limiting
- Consider producer-consumer patterns for streaming

### 3. Memory Efficiency
- Stream large files instead of loading into memory
- Use multipart uploads for files >5MB
- Implement memory pooling for repeated operations
- Consider manual garbage collection for high throughput

### 4. Multipart Optimization
- Use appropriate part sizes (8-100MB)
- Upload parts concurrently with limits
- Calculate optimal part sizes based on file size
- Implement resume capability for large uploads

### 5. Caching
- Cache metadata for frequently accessed objects
- Use appropriate TTLs for cache entries
- Implement LRU eviction for memory management
- Cache list results when possible

### 6. Monitoring
- Monitor operation timing and throughput
- Track error rates and types
- Implement alerting for performance degradation
- Use profiling tools for bottleneck identification

## Performance Benchmarking

### Benchmark Template

```python
import asyncio
import time
import statistics

async def benchmark_s3_operations(client, operations, iterations=10):
    """Benchmark S3 operations."""
    results = {}
    
    for operation_name, operation_func in operations.items():
        print(f"Benchmarking {operation_name}...")
        timings = []
        
        for i in range(iterations):
            start_time = time.perf_counter()
            try:
                await operation_func()
                duration = time.perf_counter() - start_time
                timings.append(duration)
            except Exception as e:
                print(f"  Iteration {i+1} failed: {e}")
        
        if timings:
            results[operation_name] = {
                "mean": statistics.mean(timings),
                "median": statistics.median(timings),
                "stdev": statistics.stdev(timings) if len(timings) > 1 else 0,
                "min": min(timings),
                "max": max(timings),
                "iterations": len(timings)
            }
    
    return results

# Example benchmark
async def run_benchmark():
    async with S3Client(access_key, secret_key, region) as client:
        test_data = b"x" * (1024 * 1024)  # 1MB test data
        
        operations = {
            "put_object_1mb": lambda: client.put_object("benchmark-bucket", "test-1mb.bin", test_data),
            "get_object_1mb": lambda: client.get_object("benchmark-bucket", "test-1mb.bin"),
            "head_object": lambda: client.head_object("benchmark-bucket", "test-1mb.bin"),
            "list_objects": lambda: client.list_objects("benchmark-bucket", max_keys=100),
        }
        
        results = await benchmark_s3_operations(client, operations, iterations=20)
        
        for operation, metrics in results.items():
            print(f"\n{operation}:")
            print(f"  Mean: {metrics['mean']:.3f}s")
            print(f"  Median: {metrics['median']:.3f}s")
            print(f"  Std Dev: {metrics['stdev']:.3f}s")
            print(f"  Min/Max: {metrics['min']:.3f}s / {metrics['max']:.3f}s")

# Run benchmark
await run_benchmark()
```

## Next Steps

- Review [Advanced Usage](advanced-usage.md) for complex scenarios
- Check [Error Handling](error-handling.md) for comprehensive error management
- Browse [Examples](../examples/) for complete performance optimization examples
- See [API Reference](../reference/) for detailed method documentation