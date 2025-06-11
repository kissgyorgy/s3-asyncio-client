# S3-Compatible Services Examples

The S3 Asyncio Client works with any S3-compatible storage service. This guide demonstrates how to connect to and use various popular S3-compatible services including MinIO, DigitalOcean Spaces, Wasabi, Backblaze B2, and more.

## MinIO

MinIO is a popular open-source object storage server that's S3-compatible and often used for local development and private cloud deployments.

### Basic MinIO Setup

```python
import asyncio
from s3_asyncio_client import S3Client

async def minio_example():
    # MinIO client configuration
    client = S3Client(
        access_key="minio-access-key",
        secret_key="minio-secret-key",
        region="us-east-1",  # MinIO region (can be any string)
        endpoint_url="http://localhost:9000"  # Default MinIO endpoint
    )
    
    # Test connection
    async with client:
        try:
            # List buckets to test connection
            result = await client.list_objects("test-bucket", max_keys=1)
            print("✓ Connected to MinIO successfully")
        except Exception as e:
            print(f"✗ MinIO connection failed: {e}")
    
    return client

# Run MinIO test
asyncio.run(minio_example())
```

### MinIO with Custom Configuration

```python
async def minio_custom_setup():
    """Connect to MinIO with custom configuration."""
    
    # Production MinIO setup with HTTPS
    client = S3Client(
        access_key="prod-minio-key",
        secret_key="prod-minio-secret",
        region="minio-region",
        endpoint_url="https://minio.yourcompany.com"
    )
    
    async with client:
        # Create a bucket if it doesn't exist
        try:
            await client.head_object("company-data", "test")
        except:
            print("Bucket 'company-data' might not exist")
        
        # Upload a test file
        test_data = b"Hello from MinIO!"
        result = await client.put_object(
            bucket="company-data",
            key="test/hello.txt",
            data=test_data,
            content_type="text/plain",
            metadata={
                "source": "s3-asyncio-client",
                "environment": "production"
            }
        )
        
        print(f"Uploaded to MinIO: {result['etag']}")
        
        # Download and verify
        download_result = await client.get_object(
            bucket="company-data",
            key="test/hello.txt"
        )
        
        print(f"Downloaded: {download_result['body'].decode()}")
        
        return result
```

### MinIO Deployment Example

```python
import os
from pathlib import Path

async def backup_to_minio():
    """Backup local files to MinIO server."""
    
    # MinIO server running in Docker
    # docker run -p 9000:9000 -p 9090:9090 --name minio \
    #   -e "MINIO_ROOT_USER=admin" \
    #   -e "MINIO_ROOT_PASSWORD=password123" \
    #   minio/minio server /data --console-address ":9090"
    
    client = S3Client(
        access_key="admin",
        secret_key="password123",
        region="us-east-1",
        endpoint_url="http://localhost:9000"
    )
    
    # Directory to backup
    backup_dir = Path("./documents")
    bucket_name = "file-backups"
    
    async with client:
        uploaded_files = []
        
        for file_path in backup_dir.rglob("*"):
            if file_path.is_file():
                try:
                    with open(file_path, "rb") as f:
                        file_data = f.read()
                    
                    # Create MinIO key
                    relative_path = file_path.relative_to(backup_dir)
                    minio_key = f"backups/{relative_path}"
                    
                    # Upload to MinIO
                    result = await client.put_object(
                        bucket=bucket_name,
                        key=minio_key,
                        data=file_data,
                        metadata={
                            "backup-date": datetime.now().isoformat(),
                            "original-path": str(file_path)
                        }
                    )
                    
                    uploaded_files.append({
                        "local_path": str(file_path),
                        "minio_key": minio_key,
                        "etag": result["etag"]
                    })
                    
                    print(f"✓ Backed up: {file_path} -> {minio_key}")
                    
                except Exception as e:
                    print(f"✗ Failed to backup {file_path}: {e}")
        
        print(f"Backup completed: {len(uploaded_files)} files")
        return uploaded_files
```

## DigitalOcean Spaces

DigitalOcean Spaces is a simple, reliable, and affordable object storage service.

### DigitalOcean Spaces Setup

```python
async def digitalocean_spaces_example():
    """Connect to DigitalOcean Spaces."""
    
    # DigitalOcean Spaces configuration
    client = S3Client(
        access_key="DO_SPACES_ACCESS_KEY",
        secret_key="DO_SPACES_SECRET_KEY",
        region="nyc3",  # DigitalOcean region
        endpoint_url="https://nyc3.digitaloceanspaces.com"
    )
    
    async with client:
        # Upload a file to Spaces
        image_data = open("logo.png", "rb").read()
        
        result = await client.put_object(
            bucket="my-app-assets",
            key="images/logo.png",
            data=image_data,
            content_type="image/png",
            metadata={
                "uploaded-from": "production-server",
                "category": "branding"
            }
        )
        
        print(f"Uploaded to DigitalOcean Spaces: {result['etag']}")
        
        # Generate public URL (if bucket is public)
        public_url = f"https://my-app-assets.nyc3.digitaloceanspaces.com/images/logo.png"
        print(f"Public URL: {public_url}")
        
        # Or generate presigned URL for private access
        private_url = client.generate_presigned_url(
            method="GET",
            bucket="my-app-assets",
            key="images/logo.png",
            expires_in=3600
        )
        print(f"Private URL: {private_url}")
        
        return result
```

### DigitalOcean CDN Integration

```python
async def digitalocean_cdn_setup():
    """Upload files optimized for DigitalOcean CDN."""
    
    client = S3Client(
        access_key=os.getenv("DO_SPACES_KEY"),
        secret_key=os.getenv("DO_SPACES_SECRET"),
        region="fra1",
        endpoint_url="https://fra1.digitaloceanspaces.com"
    )
    
    # Files for CDN distribution
    cdn_files = [
        {
            "local_path": "assets/css/style.css",
            "spaces_key": "cdn/css/style.css",
            "content_type": "text/css",
            "cache_control": "public, max-age=31536000"  # 1 year
        },
        {
            "local_path": "assets/js/app.js",
            "spaces_key": "cdn/js/app.js", 
            "content_type": "application/javascript",
            "cache_control": "public, max-age=86400"  # 1 day
        },
        {
            "local_path": "assets/images/hero.jpg",
            "spaces_key": "cdn/images/hero.jpg",
            "content_type": "image/jpeg",
            "cache_control": "public, max-age=604800"  # 1 week
        }
    ]
    
    async with client:
        for file_config in cdn_files:
            with open(file_config["local_path"], "rb") as f:
                file_data = f.read()
            
            # Upload with CDN-optimized headers
            result = await client.put_object(
                bucket="my-cdn-bucket",
                key=file_config["spaces_key"],
                data=file_data,
                content_type=file_config["content_type"],
                metadata={
                    "cache-control": file_config["cache_control"],
                    "cdn-optimized": "true"
                }
            )
            
            # CDN URL format
            cdn_url = f"https://my-cdn-bucket.fra1.cdn.digitaloceanspaces.com/{file_config['spaces_key']}"
            
            print(f"✓ CDN Asset: {file_config['local_path']} -> {cdn_url}")
```

## Wasabi Hot Cloud Storage

Wasabi offers affordable S3-compatible cloud storage with no egress fees.

### Wasabi Configuration

```python
async def wasabi_example():
    """Connect to Wasabi Hot Cloud Storage."""
    
    # Wasabi configuration
    client = S3Client(
        access_key="WASABI_ACCESS_KEY",
        secret_key="WASABI_SECRET_KEY",
        region="us-east-1",  # Wasabi region
        endpoint_url="https://s3.wasabisys.com"
    )
    
    async with client:
        # Upload large files efficiently (Wasabi's strength)
        large_file_path = "database-backup.sql.gz"
        
        with open(large_file_path, "rb") as f:
            file_data = f.read()
        
        print(f"Uploading {len(file_data):,} bytes to Wasabi...")
        
        # Use multipart upload for large files
        result = await client.upload_file_multipart(
            bucket="database-backups",
            key=f"daily/{datetime.now().strftime('%Y-%m-%d')}/backup.sql.gz",
            data=file_data,
            part_size=50 * 1024 * 1024,  # 50MB parts
            content_type="application/gzip",
            metadata={
                "backup-type": "daily",
                "database": "production",
                "compressed": "true"
            }
        )
        
        print(f"✓ Uploaded to Wasabi: {result['etag']}")
        
        # List recent backups
        backups = await client.list_objects(
            bucket="database-backups",
            prefix="daily/",
            max_keys=10
        )
        
        print(f"Recent backups ({len(backups['objects'])}):")
        for backup in backups["objects"]:
            size_mb = backup["size"] / 1024 / 1024
            print(f"  {backup['key']} ({size_mb:.1f} MB)")
        
        return result
```

### Wasabi Archive Solution

```python
async def wasabi_archive_system():
    """Long-term archival system using Wasabi."""
    
    client = S3Client(
        access_key=os.getenv("WASABI_ACCESS_KEY"),
        secret_key=os.getenv("WASABI_SECRET_KEY"),
        region="us-central-1",
        endpoint_url="https://s3.us-central-1.wasabisys.com"
    )
    
    # Archive old files by year
    archive_configs = {
        "documents": {
            "local_path": "./old_documents",
            "retention_years": 7
        },
        "media": {
            "local_path": "./old_media",
            "retention_years": 3
        },
        "logs": {
            "local_path": "./old_logs",
            "retention_years": 1
        }
    }
    
    async with client:
        for archive_type, config in archive_configs.items():
            archive_path = Path(config["local_path"])
            
            if not archive_path.exists():
                continue
            
            print(f"Archiving {archive_type}...")
            
            for file_path in archive_path.rglob("*"):
                if file_path.is_file():
                    # Determine archive date
                    file_date = datetime.fromtimestamp(file_path.stat().st_mtime)
                    archive_key = f"archives/{archive_type}/{file_date.year}/{file_path.name}"
                    
                    try:
                        with open(file_path, "rb") as f:
                            file_data = f.read()
                        
                        await client.put_object(
                            bucket="long-term-archive",
                            key=archive_key,
                            data=file_data,
                            metadata={
                                "archive-date": datetime.now().isoformat(),
                                "original-path": str(file_path),
                                "retention-years": str(config["retention_years"]),
                                "archive-type": archive_type
                            }
                        )
                        
                        print(f"  ✓ Archived: {file_path.name}")
                        
                    except Exception as e:
                        print(f"  ✗ Failed: {file_path.name} - {e}")
```

## Backblaze B2

Backblaze B2 provides affordable S3-compatible storage with a simple pricing model.

### Backblaze B2 Setup

```python
async def backblaze_b2_example():
    """Connect to Backblaze B2 storage."""
    
    # Backblaze B2 configuration
    client = S3Client(
        access_key="B2_APPLICATION_KEY_ID",
        secret_key="B2_APPLICATION_KEY", 
        region="us-west-002",  # Backblaze region
        endpoint_url="https://s3.us-west-002.backblazeb2.com"
    )
    
    async with client:
        # Upload with lifecycle-aware metadata
        document_data = open("important-contract.pdf", "rb").read()
        
        result = await client.put_object(
            bucket="legal-documents",
            key="contracts/2024/important-contract.pdf",
            data=document_data,
            content_type="application/pdf",
            metadata={
                "document-type": "contract",
                "retention-period": "7-years",
                "classification": "confidential",
                "uploaded-by": "legal-team"
            }
        )
        
        print(f"✓ Uploaded to Backblaze B2: {result['etag']}")
        
        # Generate secure download link
        download_url = client.generate_presigned_url(
            method="GET",
            bucket="legal-documents",
            key="contracts/2024/important-contract.pdf",
            expires_in=24 * 3600  # 24 hours
        )
        
        print(f"Secure download URL: {download_url}")
        
        return result
```

## IBM Cloud Object Storage

IBM Cloud Object Storage is enterprise-grade S3-compatible storage.

### IBM Cloud Setup

```python
async def ibm_cloud_example():
    """Connect to IBM Cloud Object Storage."""
    
    # IBM Cloud Object Storage configuration
    client = S3Client(
        access_key="IBM_CLOUD_ACCESS_KEY",
        secret_key="IBM_CLOUD_SECRET_KEY",
        region="us-south",
        endpoint_url="https://s3.us-south.cloud-object-storage.appdomain.cloud"
    )
    
    async with client:
        # Enterprise data upload with compliance metadata
        sensitive_data = b"Confidential business data..."
        
        result = await client.put_object(
            bucket="enterprise-data",
            key="compliance/financial/q4-2024-report.json",
            data=sensitive_data,
            content_type="application/json",
            metadata={
                "data-classification": "confidential",
                "compliance-requirement": "SOX",
                "retention-period": "7-years",
                "encryption-required": "true",
                "access-level": "executive-only"
            }
        )
        
        print(f"✓ Uploaded to IBM Cloud: {result['etag']}")
        
        return result
```

## Oracle Cloud Infrastructure (OCI)

Oracle Cloud Infrastructure Object Storage with S3 compatibility.

### OCI Configuration

```python
async def oci_example():
    """Connect to Oracle Cloud Infrastructure Object Storage."""
    
    # OCI Object Storage configuration
    client = S3Client(
        access_key="OCI_ACCESS_KEY",
        secret_key="OCI_SECRET_KEY",
        region="us-ashburn-1",
        endpoint_url="https://namespace.compat.objectstorage.us-ashburn-1.oraclecloud.com"
    )
    
    async with client:
        # Upload with OCI-specific optimizations
        database_export = open("oracle_export.dmp", "rb").read()
        
        result = await client.upload_file_multipart(
            bucket="database-exports",
            key=f"exports/{datetime.now().strftime('%Y/%m/%d')}/oracle_export.dmp",
            data=database_export,
            part_size=100 * 1024 * 1024,  # 100MB parts for OCI
            content_type="application/octet-stream",
            metadata={
                "export-type": "full",
                "database-version": "19c",
                "export-tool": "expdp"
            }
        )
        
        print(f"✓ Uploaded to OCI: {result['etag']}")
        
        return result
```

## Multi-Cloud Storage Strategy

### Cloud-Agnostic Storage Manager

```python
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List

class CloudProvider(Enum):
    AWS_S3 = "aws_s3"
    MINIO = "minio"
    DIGITALOCEAN = "digitalocean"
    WASABI = "wasabi"
    BACKBLAZE = "backblaze"
    IBM_CLOUD = "ibm_cloud"
    ORACLE_CLOUD = "oracle_cloud"

@dataclass
class CloudConfig:
    provider: CloudProvider
    access_key: str
    secret_key: str
    region: str
    endpoint_url: str
    bucket: str

class MultiCloudStorageManager:
    """Manage files across multiple S3-compatible cloud providers."""
    
    def __init__(self):
        self.clients: Dict[CloudProvider, S3Client] = {}
        self.configs: Dict[CloudProvider, CloudConfig] = {}
    
    def add_provider(self, config: CloudConfig):
        """Add a cloud storage provider."""
        self.configs[config.provider] = config
        
        client = S3Client(
            access_key=config.access_key,
            secret_key=config.secret_key,
            region=config.region,
            endpoint_url=config.endpoint_url
        )
        
        self.clients[config.provider] = client
    
    async def upload_to_multiple(
        self,
        file_data: bytes,
        key: str,
        providers: List[CloudProvider],
        content_type: str = "application/octet-stream",
        metadata: Dict[str, str] = None
    ) -> Dict[CloudProvider, Dict]:
        """Upload file to multiple cloud providers."""
        
        results = {}
        
        for provider in providers:
            if provider not in self.clients:
                continue
            
            try:
                client = self.clients[provider]
                config = self.configs[provider]
                
                async with client:
                    result = await client.put_object(
                        bucket=config.bucket,
                        key=key,
                        data=file_data,
                        content_type=content_type,
                        metadata={
                            **(metadata or {}),
                            "provider": provider.value,
                            "multi-cloud-upload": "true"
                        }
                    )
                    
                    results[provider] = {
                        "success": True,
                        "etag": result["etag"],
                        "provider": provider.value
                    }
                    
                    print(f"✓ Uploaded to {provider.value}: {key}")
                    
            except Exception as e:
                results[provider] = {
                    "success": False,
                    "error": str(e),
                    "provider": provider.value
                }
                
                print(f"✗ Failed to upload to {provider.value}: {e}")
        
        return results
    
    async def download_from_best_provider(
        self,
        key: str,
        preferred_order: List[CloudProvider] = None
    ) -> tuple[bytes, CloudProvider]:
        """Download file from the first available provider."""
        
        if not preferred_order:
            preferred_order = list(self.clients.keys())
        
        for provider in preferred_order:
            if provider not in self.clients:
                continue
            
            try:
                client = self.clients[provider]
                config = self.configs[provider]
                
                async with client:
                    result = await client.get_object(
                        bucket=config.bucket,
                        key=key
                    )
                    
                    print(f"✓ Downloaded from {provider.value}: {key}")
                    return result["body"], provider
                    
            except Exception as e:
                print(f"✗ Failed to download from {provider.value}: {e}")
                continue
        
        raise Exception("File not found in any configured provider")
    
    async def sync_across_providers(
        self,
        source_provider: CloudProvider,
        target_providers: List[CloudProvider],
        key_prefix: str = ""
    ) -> Dict:
        """Sync files from one provider to others."""
        
        if source_provider not in self.clients:
            raise ValueError(f"Source provider {source_provider} not configured")
        
        source_client = self.clients[source_provider]
        source_config = self.configs[source_provider]
        
        sync_results = {"synced": [], "failed": []}
        
        async with source_client:
            # List files to sync
            files_result = await source_client.list_objects(
                bucket=source_config.bucket,
                prefix=key_prefix,
                max_keys=1000
            )
            
            for file_obj in files_result["objects"]:
                key = file_obj["key"]
                
                try:
                    # Download from source
                    download_result = await source_client.get_object(
                        bucket=source_config.bucket,
                        key=key
                    )
                    
                    # Upload to target providers
                    upload_results = await self.upload_to_multiple(
                        file_data=download_result["body"],
                        key=key,
                        providers=target_providers,
                        content_type=download_result["content_type"],
                        metadata={
                            "synced-from": source_provider.value,
                            "sync-date": datetime.now().isoformat()
                        }
                    )
                    
                    sync_results["synced"].append({
                        "key": key,
                        "results": upload_results
                    })
                    
                except Exception as e:
                    sync_results["failed"].append({
                        "key": key,
                        "error": str(e)
                    })
        
        return sync_results

# Example usage
async def multi_cloud_example():
    """Example of multi-cloud storage management."""
    
    manager = MultiCloudStorageManager()
    
    # Configure multiple providers
    manager.add_provider(CloudConfig(
        provider=CloudProvider.AWS_S3,
        access_key="aws-key",
        secret_key="aws-secret",
        region="us-east-1",
        endpoint_url="https://s3.amazonaws.com",
        bucket="aws-backup"
    ))
    
    manager.add_provider(CloudConfig(
        provider=CloudProvider.MINIO,
        access_key="minio-key",
        secret_key="minio-secret", 
        region="us-east-1",
        endpoint_url="http://localhost:9000",
        bucket="minio-backup"
    ))
    
    manager.add_provider(CloudConfig(
        provider=CloudProvider.DIGITALOCEAN,
        access_key="do-key",
        secret_key="do-secret",
        region="nyc3",
        endpoint_url="https://nyc3.digitaloceanspaces.com",
        bucket="do-backup"
    ))
    
    # Upload to multiple providers for redundancy
    important_data = b"Critical business data that needs multiple backups"
    
    results = await manager.upload_to_multiple(
        file_data=important_data,
        key="critical/business-data.bin",
        providers=[
            CloudProvider.AWS_S3,
            CloudProvider.MINIO,
            CloudProvider.DIGITALOCEAN
        ],
        metadata={
            "importance": "critical",
            "backup-strategy": "multi-cloud"
        }
    )
    
    print("Multi-cloud upload results:")
    for provider, result in results.items():
        status = "✓" if result["success"] else "✗"
        print(f"  {status} {provider.value}: {result}")
    
    # Download from best available provider
    try:
        data, provider = await manager.download_from_best_provider(
            key="critical/business-data.bin",
            preferred_order=[
                CloudProvider.MINIO,  # Try local first
                CloudProvider.DIGITALOCEAN,  # Then regional
                CloudProvider.AWS_S3  # Finally global
            ]
        )
        print(f"Successfully downloaded from {provider.value}")
    except Exception as e:
        print(f"Download failed: {e}")

# Run multi-cloud example
if __name__ == "__main__":
    asyncio.run(multi_cloud_example())
```

## Configuration Management

### Environment-Based Configuration

```python
import os
from typing import Optional

class S3CompatibleConfig:
    """Centralized configuration for S3-compatible services."""
    
    # Service endpoint configurations
    ENDPOINTS = {
        "aws": "https://s3.{region}.amazonaws.com",
        "minio": os.getenv("MINIO_ENDPOINT", "http://localhost:9000"),
        "digitalocean": "https://{region}.digitaloceanspaces.com",
        "wasabi": "https://s3.wasabisys.com",
        "backblaze": "https://s3.{region}.backblazeb2.com",
        "ibm": "https://s3.{region}.cloud-object-storage.appdomain.cloud",
        "oracle": "https://namespace.compat.objectstorage.{region}.oraclecloud.com"
    }
    
    @classmethod
    def create_client(
        cls,
        service: str,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        region: str = "us-east-1",
        endpoint_url: Optional[str] = None
    ) -> S3Client:
        """Create S3Client for specific service."""
        
        # Get credentials from environment if not provided
        if not access_key:
            access_key = os.getenv(f"{service.upper()}_ACCESS_KEY")
        if not secret_key:
            secret_key = os.getenv(f"{service.upper()}_SECRET_KEY")
        
        if not access_key or not secret_key:
            raise ValueError(f"Missing credentials for {service}")
        
        # Determine endpoint URL
        if not endpoint_url:
            if service in cls.ENDPOINTS:
                endpoint_url = cls.ENDPOINTS[service].format(region=region)
            else:
                raise ValueError(f"Unknown service: {service}")
        
        return S3Client(
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            endpoint_url=endpoint_url
        )

# Usage examples
async def config_examples():
    """Examples using centralized configuration."""
    
    # AWS S3
    aws_client = S3CompatibleConfig.create_client(
        service="aws",
        region="us-west-2"
    )
    
    # MinIO
    minio_client = S3CompatibleConfig.create_client(
        service="minio"
    )
    
    # DigitalOcean Spaces
    do_client = S3CompatibleConfig.create_client(
        service="digitalocean",
        region="fra1"
    )
    
    # Test all clients
    clients = [
        ("AWS S3", aws_client),
        ("MinIO", minio_client),
        ("DigitalOcean", do_client)
    ]
    
    for name, client in clients:
        try:
            async with client:
                # Simple connectivity test
                result = await client.list_objects("test", max_keys=1)
                print(f"✓ {name}: Connected successfully")
        except Exception as e:
            print(f"✗ {name}: {e}")

# Environment variables setup example
"""
# .env file
AWS_ACCESS_KEY=your-aws-access-key
AWS_SECRET_KEY=your-aws-secret-key

MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=password123
MINIO_ENDPOINT=http://localhost:9000

DIGITALOCEAN_ACCESS_KEY=your-do-spaces-key
DIGITALOCEAN_SECRET_KEY=your-do-spaces-secret

WASABI_ACCESS_KEY=your-wasabi-key
WASABI_SECRET_KEY=your-wasabi-secret
"""
```

This comprehensive guide demonstrates how to use the S3 Asyncio Client with various S3-compatible services. Each service has its own strengths and use cases, and the client works seamlessly with all of them using the same simple interface.