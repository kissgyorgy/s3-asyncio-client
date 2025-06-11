# Presigned URL Examples

Presigned URLs allow you to grant temporary access to S3 objects without exposing your AWS credentials. This is essential for web applications, mobile apps, and third-party integrations.

## What are Presigned URLs?

Presigned URLs are time-limited URLs that include authentication information, allowing anyone with the URL to perform specific S3 operations (GET, PUT, etc.) without needing AWS credentials.

## Common Use Cases

- **Direct uploads from web browsers**: Let users upload files directly to S3
- **Secure file sharing**: Share files temporarily without making them public
- **Mobile app file access**: Allow mobile apps to access S3 without embedded credentials
- **Third-party integrations**: Grant temporary access to external services
- **Content delivery**: Serve private content through CDNs

## Basic Presigned URL Generation

### Download URLs (GET)

```python
import asyncio
from s3_asyncio_client import S3Client

async def create_download_urls():
    client = S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key",
        region="us-east-1"
    )
    
    # Create a presigned URL for downloading a file
    download_url = client.generate_presigned_url(
        method="GET",
        bucket="my-private-bucket",
        key="documents/secret-report.pdf",
        expires_in=3600  # 1 hour
    )
    
    print(f"Download URL (valid for 1 hour):")
    print(download_url)
    
    # URL can now be used by anyone to download the file
    # Example: curl "https://my-private-bucket.s3.amazonaws.com/documents/secret-report.pdf?X-Amz-Algorithm=..."
    
    return download_url

# Generate download URL
asyncio.run(create_download_urls())
```

### Upload URLs (PUT)

```python
async def create_upload_urls():
    client = S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key",
        region="us-east-1"
    )
    
    # Create a presigned URL for uploading a file
    upload_url = client.generate_presigned_url(
        method="PUT",
        bucket="user-uploads",
        key="uploads/user-123/profile-photo.jpg",
        expires_in=1800,  # 30 minutes
        params={
            "Content-Type": "image/jpeg"
        }
    )
    
    print(f"Upload URL (valid for 30 minutes):")
    print(upload_url)
    
    # Client can upload using:
    # curl -X PUT "upload_url" -H "Content-Type: image/jpeg" --data-binary "@photo.jpg"
    
    return upload_url
```

## Web Application Integration

### Backend API for File Uploads

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uuid
from datetime import datetime

app = FastAPI()

class UploadRequest(BaseModel):
    filename: str
    content_type: str
    file_size: int

class UploadResponse(BaseModel):
    upload_url: str
    key: str
    expires_in: int

@app.post("/api/get-upload-url", response_model=UploadResponse)
async def get_upload_url(request: UploadRequest):
    """Generate presigned URL for file upload."""
    
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "application/pdf", "text/plain"]
    if request.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="File type not allowed")
    
    # Validate file size (10MB limit)
    if request.file_size > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large")
    
    # Create unique key
    file_extension = request.filename.split('.')[-1]
    unique_key = f"uploads/{datetime.now().strftime('%Y/%m/%d')}/{uuid.uuid4()}.{file_extension}"
    
    # Generate presigned URL
    client = S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    )
    
    upload_url = client.generate_presigned_url(
        method="PUT",
        bucket="user-uploads",
        key=unique_key,
        expires_in=3600,  # 1 hour
        params={
            "Content-Type": request.content_type,
            "Content-Length": str(request.file_size)
        }
    )
    
    return UploadResponse(
        upload_url=upload_url,
        key=unique_key,
        expires_in=3600
    )

@app.post("/api/confirm-upload")
async def confirm_upload(key: str):
    """Confirm that upload was completed successfully."""
    client = S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    )
    
    try:
        # Verify file exists
        async with client:
            metadata = await client.head_object(
                bucket="user-uploads",
                key=key
            )
        
        return {
            "status": "success",
            "file_size": metadata["content_length"],
            "upload_time": metadata["last_modified"]
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail="Upload not found or failed")
```

### Frontend JavaScript Integration

```html
<!DOCTYPE html>
<html>
<head>
    <title>Direct S3 Upload</title>
</head>
<body>
    <input type="file" id="fileInput" />
    <button onclick="uploadFile()">Upload to S3</button>
    <div id="progress"></div>

    <script>
    async function uploadFile() {
        const fileInput = document.getElementById('fileInput');
        const progressDiv = document.getElementById('progress');
        
        if (!fileInput.files[0]) {
            alert('Please select a file');
            return;
        }
        
        const file = fileInput.files[0];
        
        try {
            // Step 1: Get presigned URL from backend
            progressDiv.innerHTML = 'Getting upload URL...';
            
            const response = await fetch('/api/get-upload-url', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    filename: file.name,
                    content_type: file.type,
                    file_size: file.size
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to get upload URL');
            }
            
            const { upload_url, key } = await response.json();
            
            // Step 2: Upload directly to S3
            progressDiv.innerHTML = 'Uploading to S3...';
            
            const uploadResponse = await fetch(upload_url, {
                method: 'PUT',
                headers: {
                    'Content-Type': file.type,
                },
                body: file
            });
            
            if (!uploadResponse.ok) {
                throw new Error('Upload failed');
            }
            
            // Step 3: Confirm upload with backend
            progressDiv.innerHTML = 'Confirming upload...';
            
            const confirmResponse = await fetch('/api/confirm-upload', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ key })
            });
            
            if (confirmResponse.ok) {
                progressDiv.innerHTML = 'Upload successful!';
            } else {
                throw new Error('Upload confirmation failed');
            }
            
        } catch (error) {
            progressDiv.innerHTML = `Error: ${error.message}`;
            console.error('Upload error:', error);
        }
    }
    </script>
</body>
</html>
```

## Advanced Presigned URL Scenarios

### Secure File Sharing with Expiration

```python
async def create_secure_share_link():
    """Create secure, time-limited sharing links."""
    client = S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    )
    
    # Create different expiration times based on file sensitivity
    file_configs = [
        {
            "key": "public-documents/newsletter.pdf",
            "expires_in": 7 * 24 * 3600,  # 7 days
            "description": "Newsletter (public)"
        },
        {
            "key": "confidential/financial-report.pdf", 
            "expires_in": 2 * 3600,  # 2 hours
            "description": "Financial report (confidential)"
        },
        {
            "key": "temp-files/meeting-recording.mp4",
            "expires_in": 24 * 3600,  # 24 hours
            "description": "Meeting recording (temporary)"
        }
    ]
    
    share_links = []
    
    for config in file_configs:
        # Generate download URL with custom expiration
        download_url = client.generate_presigned_url(
            method="GET",
            bucket="secure-documents",
            key=config["key"],
            expires_in=config["expires_in"],
            params={
                "response-content-disposition": f"attachment; filename=\"{config['key'].split('/')[-1]}\""
            }
        )
        
        share_links.append({
            "description": config["description"],
            "url": download_url,
            "expires_hours": config["expires_in"] // 3600
        })
        
        print(f"{config['description']}:")
        print(f"  URL: {download_url}")
        print(f"  Expires in: {config['expires_in'] // 3600} hours")
        print()
    
    return share_links
```

### Batch Presigned URL Generation

```python
async def generate_batch_urls():
    """Generate presigned URLs for multiple files efficiently."""
    client = S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    )
    
    # List of files to create URLs for
    files_to_share = [
        "reports/2024/january.pdf",
        "reports/2024/february.pdf", 
        "reports/2024/march.pdf",
        "reports/2024/april.pdf",
        "images/chart1.png",
        "images/chart2.png",
        "data/raw-data.csv"
    ]
    
    # Generate URLs for all files
    batch_urls = {}
    
    for file_key in files_to_share:
        # Different expiration based on file type
        if file_key.endswith('.pdf'):
            expires_in = 48 * 3600  # 48 hours for PDFs
        elif file_key.endswith('.png'):
            expires_in = 7 * 24 * 3600  # 7 days for images
        else:
            expires_in = 24 * 3600  # 24 hours for others
        
        url = client.generate_presigned_url(
            method="GET",
            bucket="report-sharing",
            key=file_key,
            expires_in=expires_in
        )
        
        batch_urls[file_key] = {
            "url": url,
            "expires_in_hours": expires_in // 3600
        }
    
    # Output as JSON for API response
    import json
    print(json.dumps(batch_urls, indent=2))
    
    return batch_urls
```

### Mobile App Integration

```python
from typing import Dict, List
import jwt
from datetime import datetime, timedelta

class MobileAppURLService:
    """Service for generating presigned URLs for mobile apps."""
    
    def __init__(self):
        self.client = S3Client(
            access_key="your-access-key",
            secret_key="your-secret-key"
        )
        self.jwt_secret = "your-jwt-secret"
    
    def verify_mobile_token(self, token: str) -> Dict:
        """Verify mobile app JWT token."""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            raise Exception("Token expired")
        except jwt.InvalidTokenError:
            raise Exception("Invalid token")
    
    async def get_user_upload_urls(self, auth_token: str, file_requests: List[Dict]) -> Dict:
        """Generate presigned URLs for authenticated mobile user."""
        
        # Verify user authentication
        user_data = self.verify_mobile_token(auth_token)
        user_id = user_data["user_id"]
        
        upload_urls = []
        
        for file_request in file_requests:
            filename = file_request["filename"]
            content_type = file_request["content_type"]
            file_size = file_request.get("file_size", 0)
            
            # Validate file size (mobile apps often have limits)
            if file_size > 50 * 1024 * 1024:  # 50MB limit
                continue
            
            # Create user-specific key
            file_extension = filename.split('.')[-1] if '.' in filename else 'bin'
            unique_key = f"mobile-uploads/{user_id}/{datetime.now().strftime('%Y/%m/%d')}/{uuid.uuid4()}.{file_extension}"
            
            # Generate presigned URL
            upload_url = self.client.generate_presigned_url(
                method="PUT",
                bucket="mobile-app-uploads",
                key=unique_key,
                expires_in=1800,  # 30 minutes
                params={
                    "Content-Type": content_type
                }
            )
            
            upload_urls.append({
                "original_filename": filename,
                "upload_url": upload_url,
                "key": unique_key,
                "expires_at": (datetime.now() + timedelta(minutes=30)).isoformat()
            })
        
        return {
            "user_id": user_id,
            "upload_urls": upload_urls,
            "expires_in": 1800
        }
    
    async def get_user_download_urls(self, auth_token: str, file_keys: List[str]) -> Dict:
        """Generate presigned URLs for user to download their files."""
        
        user_data = self.verify_mobile_token(auth_token)
        user_id = user_data["user_id"]
        
        download_urls = []
        
        for key in file_keys:
            # Verify user owns this file
            if not key.startswith(f"mobile-uploads/{user_id}/"):
                continue  # Skip files not owned by user
            
            # Check if file exists
            try:
                async with self.client:
                    await self.client.head_object("mobile-app-uploads", key)
            except:
                continue  # Skip non-existent files
            
            # Generate download URL
            download_url = self.client.generate_presigned_url(
                method="GET",
                bucket="mobile-app-uploads",
                key=key,
                expires_in=3600  # 1 hour
            )
            
            download_urls.append({
                "key": key,
                "download_url": download_url,
                "expires_at": (datetime.now() + timedelta(hours=1)).isoformat()
            })
        
        return {
            "user_id": user_id,
            "download_urls": download_urls
        }

# Example usage in mobile API
mobile_service = MobileAppURLService()

@app.post("/mobile/upload-urls")
async def mobile_upload_urls(auth_token: str, files: List[Dict]):
    try:
        result = await mobile_service.get_user_upload_urls(auth_token, files)
        return result
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
```

### CDN Integration with Presigned URLs

```python
async def create_cdn_compatible_urls():
    """Create presigned URLs that work with CloudFront CDN."""
    client = S3Client(
        access_key="your-access-key",
        secret_key="your-secret-key"
    )
    
    # For files that need CDN caching
    media_files = [
        "media/images/hero-banner.jpg",
        "media/videos/product-demo.mp4",
        "media/documents/user-manual.pdf"
    ]
    
    cdn_urls = []
    
    for file_key in media_files:
        # Create presigned URL with cache-friendly parameters
        presigned_url = client.generate_presigned_url(
            method="GET",
            bucket="cdn-content",
            key=file_key,
            expires_in=24 * 3600,  # 24 hours
            params={
                "response-cache-control": "public, max-age=3600",  # 1 hour cache
                "response-content-type": "application/octet-stream"
            }
        )
        
        # Convert S3 URL to CloudFront URL
        cloudfront_domain = "d1234567890.cloudfront.net"
        s3_domain = "cdn-content.s3.amazonaws.com"
        
        cdn_url = presigned_url.replace(s3_domain, cloudfront_domain)
        
        cdn_urls.append({
            "file": file_key,
            "s3_url": presigned_url,
            "cdn_url": cdn_url
        })
        
        print(f"File: {file_key}")
        print(f"  S3 URL: {presigned_url}")
        print(f"  CDN URL: {cdn_url}")
        print()
    
    return cdn_urls
```

## Security Best Practices

### URL Validation and Sanitization

```python
import re
from urllib.parse import urlparse, parse_qs

class SecurePresignedURLGenerator:
    """Secure presigned URL generator with validation."""
    
    def __init__(self):
        self.client = S3Client(
            access_key="your-access-key",
            secret_key="your-secret-key"
        )
        
        # Allowed file extensions
        self.allowed_extensions = {
            'images': ['.jpg', '.jpeg', '.png', '.gif', '.webp'],
            'documents': ['.pdf', '.doc', '.docx', '.txt'],
            'videos': ['.mp4', '.mov', '.avi'],
            'data': ['.csv', '.json', '.xml']
        }
    
    def validate_file_key(self, key: str, category: str) -> bool:
        """Validate file key for security."""
        
        # Check for path traversal attempts
        if '..' in key or key.startswith('/'):
            return False
        
        # Check file extension
        file_ext = '.' + key.split('.')[-1].lower() if '.' in key else ''
        if file_ext not in self.allowed_extensions.get(category, []):
            return False
        
        # Check key length
        if len(key) > 1000:
            return False
        
        # Check for suspicious characters
        if re.search(r'[<>:"|?*]', key):
            return False
        
        return True
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for S3 key."""
        # Remove or replace dangerous characters
        sanitized = re.sub(r'[<>:"|?*\\]', '_', filename)
        sanitized = re.sub(r'\.\.+', '.', sanitized)  # Remove multiple dots
        sanitized = sanitized.strip('. ')  # Remove leading/trailing dots and spaces
        
        return sanitized[:255]  # Limit length
    
    async def create_secure_upload_url(
        self, 
        user_id: str, 
        filename: str, 
        category: str,
        max_file_size: int = 10 * 1024 * 1024  # 10MB default
    ) -> Dict:
        """Create secure presigned upload URL."""
        
        # Sanitize filename
        safe_filename = self.sanitize_filename(filename)
        
        # Create secure key
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        secure_key = f"uploads/{category}/{user_id}/{timestamp}_{unique_id}_{safe_filename}"
        
        # Validate key
        if not self.validate_file_key(secure_key, category):
            raise ValueError("Invalid file for upload")
        
        # Generate presigned URL with size limit
        upload_url = self.client.generate_presigned_url(
            method="PUT",
            bucket="secure-uploads",
            key=secure_key,
            expires_in=1800,  # 30 minutes
            params={
                "Content-Length": str(max_file_size)  # Enforce size limit
            }
        )
        
        return {
            "upload_url": upload_url,
            "key": secure_key,
            "max_size": max_file_size,
            "expires_in": 1800,
            "original_filename": filename,
            "sanitized_filename": safe_filename
        }

# Usage example
secure_generator = SecurePresignedURLGenerator()

@app.post("/secure-upload-url")
async def get_secure_upload_url(
    user_id: str,
    filename: str,
    category: str,
    max_size: int = 10 * 1024 * 1024
):
    try:
        result = await secure_generator.create_secure_upload_url(
            user_id=user_id,
            filename=filename,
            category=category,
            max_file_size=max_size
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### Rate Limiting for Presigned URLs

```python
import time
from collections import defaultdict, deque

class RateLimitedURLGenerator:
    """Presigned URL generator with rate limiting."""
    
    def __init__(self):
        self.client = S3Client(
            access_key="your-access-key",
            secret_key="your-secret-key"
        )
        
        # Rate limiting: max 10 URLs per minute per user
        self.rate_limit = 10
        self.time_window = 60  # seconds
        self.user_requests = defaultdict(deque)
    
    def check_rate_limit(self, user_id: str) -> bool:
        """Check if user is within rate limits."""
        now = time.time()
        user_queue = self.user_requests[user_id]
        
        # Remove old requests outside time window
        while user_queue and now - user_queue[0] > self.time_window:
            user_queue.popleft()
        
        # Check if under limit
        if len(user_queue) >= self.rate_limit:
            return False
        
        # Add current request
        user_queue.append(now)
        return True
    
    async def create_rate_limited_url(self, user_id: str, **kwargs) -> Dict:
        """Create presigned URL with rate limiting."""
        
        if not self.check_rate_limit(user_id):
            raise Exception(f"Rate limit exceeded. Max {self.rate_limit} requests per {self.time_window} seconds")
        
        # Generate URL normally
        url = self.client.generate_presigned_url(**kwargs)
        
        return {
            "url": url,
            "user_id": user_id,
            "created_at": datetime.now().isoformat()
        }

# Usage
rate_limited_generator = RateLimitedURLGenerator()

@app.post("/rate-limited-url")
async def get_rate_limited_url(user_id: str, bucket: str, key: str):
    try:
        result = await rate_limited_generator.create_rate_limited_url(
            user_id=user_id,
            method="GET",
            bucket=bucket,
            key=key,
            expires_in=3600
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=429, detail=str(e))
```

## Complete Example: File Sharing Service

```python
import asyncio
import sqlite3
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional

@dataclass
class SharedFile:
    id: str
    owner_id: str
    file_key: str
    bucket: str
    expires_at: datetime
    download_count: int
    max_downloads: Optional[int]
    password: Optional[str]

class FileShareService:
    """Complete file sharing service using presigned URLs."""
    
    def __init__(self):
        self.client = S3Client(
            access_key="your-access-key",
            secret_key="your-secret-key"
        )
        self.db = sqlite3.connect("file_shares.db")
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS shared_files (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                file_key TEXT NOT NULL,
                bucket TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                download_count INTEGER DEFAULT 0,
                max_downloads INTEGER,
                password TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.db.commit()
    
    async def create_share_link(
        self,
        owner_id: str,
        bucket: str,
        file_key: str,
        expires_hours: int = 24,
        max_downloads: Optional[int] = None,
        password: Optional[str] = None
    ) -> Dict:
        """Create a shareable link for a file."""
        
        # Verify file exists
        async with self.client:
            try:
                file_info = await self.client.head_object(bucket, file_key)
            except Exception:
                raise ValueError("File not found")
        
        # Generate unique share ID
        share_id = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(hours=expires_hours)
        
        # Store share information
        self.db.execute(
            """INSERT INTO shared_files 
               (id, owner_id, file_key, bucket, expires_at, max_downloads, password)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (share_id, owner_id, file_key, bucket, expires_at, max_downloads, password)
        )
        self.db.commit()
        
        # Create share URL (not the actual S3 URL yet)
        share_url = f"https://yourapp.com/share/{share_id}"
        
        return {
            "share_id": share_id,
            "share_url": share_url,
            "expires_at": expires_at.isoformat(),
            "max_downloads": max_downloads,
            "password_protected": password is not None,
            "file_info": {
                "key": file_key,
                "size": file_info["content_length"],
                "content_type": file_info["content_type"]
            }
        }
    
    async def get_download_url(
        self,
        share_id: str,
        password: Optional[str] = None
    ) -> Dict:
        """Get actual download URL for a shared file."""
        
        # Get share information
        cursor = self.db.execute(
            "SELECT * FROM shared_files WHERE id = ?",
            (share_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            raise ValueError("Share not found")
        
        # Parse row data
        (id, owner_id, file_key, bucket, expires_at_str, 
         download_count, max_downloads, stored_password) = row[:8]
        
        expires_at = datetime.fromisoformat(expires_at_str)
        
        # Check if expired
        if datetime.now() > expires_at:
            raise ValueError("Share has expired")
        
        # Check download limit
        if max_downloads and download_count >= max_downloads:
            raise ValueError("Download limit reached")
        
        # Check password
        if stored_password and password != stored_password:
            raise ValueError("Invalid password")
        
        # Generate presigned URL
        download_url = self.client.generate_presigned_url(
            method="GET",
            bucket=bucket,
            key=file_key,
            expires_in=3600,  # 1 hour
            params={
                "response-content-disposition": f"attachment; filename=\"{file_key.split('/')[-1]}\""
            }
        )
        
        # Increment download count
        self.db.execute(
            "UPDATE shared_files SET download_count = download_count + 1 WHERE id = ?",
            (share_id,)
        )
        self.db.commit()
        
        return {
            "download_url": download_url,
            "filename": file_key.split('/')[-1],
            "expires_in": 3600,
            "downloads_remaining": max_downloads - download_count - 1 if max_downloads else None
        }
    
    async def list_user_shares(self, owner_id: str) -> List[Dict]:
        """List all shares created by a user."""
        cursor = self.db.execute(
            """SELECT id, file_key, expires_at, download_count, max_downloads
               FROM shared_files WHERE owner_id = ?
               ORDER BY created_at DESC""",
            (owner_id,)
        )
        
        shares = []
        for row in cursor.fetchall():
            share_id, file_key, expires_at_str, download_count, max_downloads = row
            
            shares.append({
                "share_id": share_id,
                "filename": file_key.split('/')[-1],
                "expires_at": expires_at_str,
                "download_count": download_count,
                "max_downloads": max_downloads,
                "share_url": f"https://yourapp.com/share/{share_id}",
                "active": datetime.fromisoformat(expires_at_str) > datetime.now()
            })
        
        return shares
    
    def cleanup_expired_shares(self):
        """Remove expired shares from database."""
        self.db.execute(
            "DELETE FROM shared_files WHERE expires_at < ?",
            (datetime.now(),)
        )
        self.db.commit()

# Example FastAPI integration
share_service = FileShareService()

@app.post("/share/create")
async def create_file_share(
    owner_id: str,
    bucket: str,
    file_key: str,
    expires_hours: int = 24,
    max_downloads: Optional[int] = None,
    password: Optional[str] = None
):
    try:
        result = await share_service.create_share_link(
            owner_id=owner_id,
            bucket=bucket,
            file_key=file_key,
            expires_hours=expires_hours,
            max_downloads=max_downloads,
            password=password
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/share/{share_id}")
async def get_shared_file(share_id: str, password: Optional[str] = None):
    try:
        result = await share_service.get_download_url(share_id, password)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/share/user/{owner_id}")
async def list_user_file_shares(owner_id: str):
    shares = await share_service.list_user_shares(owner_id)
    return {"shares": shares}

# Cleanup job (run periodically)
@app.post("/admin/cleanup-expired")
async def cleanup_expired():
    share_service.cleanup_expired_shares()
    return {"status": "cleanup completed"}
```