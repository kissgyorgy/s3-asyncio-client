"""AWS Signature Version 4 authentication for S3."""

import hashlib
import hmac
import urllib.parse
from datetime import datetime


class AWSSignatureV4:
    """AWS Signature Version 4 authentication handler."""

    def __init__(
        self,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
        service: str = "s3",
    ):
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.service = service

    def _sha256_hash(self, data: bytes) -> str:
        """Create SHA256 hash of data."""
        return hashlib.sha256(data).hexdigest()

    def _hmac_sha256(self, key: bytes, data: str) -> bytes:
        """Create HMAC-SHA256 signature."""
        return hmac.new(key, data.encode("utf-8"), hashlib.sha256).digest()

    def _get_signature_key(self, date_stamp: str) -> bytes:
        """Derive the signing key for AWS Signature Version 4."""
        k_date = self._hmac_sha256(f"AWS4{self.secret_key}".encode(), date_stamp)
        k_region = self._hmac_sha256(k_date, self.region)
        k_service = self._hmac_sha256(k_region, self.service)
        k_signing = self._hmac_sha256(k_service, "aws4_request")
        return k_signing

    def _create_canonical_request(
        self,
        method: str,
        uri: str,
        query_string: str,
        headers: dict[str, str],
        signed_headers: str,
        payload_hash: str,
    ) -> str:
        """Create canonical request for AWS Signature Version 4."""
        canonical_uri = urllib.parse.quote(uri, safe="/~")
        canonical_querystring = query_string
        canonical_headers = ""

        # Sort headers and create canonical headers string
        for header_name in sorted(headers.keys()):
            header_value = headers[header_name].strip()
            canonical_headers += f"{header_name.lower()}:{header_value}\n"

        canonical_request = "\n".join(
            [
                method,
                canonical_uri,
                canonical_querystring,
                canonical_headers,
                signed_headers,
                payload_hash,
            ]
        )

        return canonical_request

    def _create_string_to_sign(
        self,
        timestamp: str,
        date_stamp: str,
        canonical_request: str,
    ) -> str:
        """Create string to sign for AWS Signature Version 4."""
        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{self.region}/{self.service}/aws4_request"
        string_to_sign = "\n".join(
            [
                algorithm,
                timestamp,
                credential_scope,
                self._sha256_hash(canonical_request.encode("utf-8")),
            ]
        )
        return string_to_sign

    def sign_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        payload: bytes = b"",
        query_params: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Sign an HTTP request using AWS Signature Version 4."""
        if headers is None:
            headers = {}

        if query_params is None:
            query_params = {}

        # Parse URL
        parsed_url = urllib.parse.urlparse(url)
        host = parsed_url.netloc
        uri = parsed_url.path or "/"

        # Create timestamp
        now = datetime.utcnow()
        timestamp = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        # Add required headers
        headers = headers.copy()
        headers["host"] = host
        headers["x-amz-date"] = timestamp

        # Handle payload hash
        if "x-amz-content-sha256" not in headers:
            headers["x-amz-content-sha256"] = self._sha256_hash(payload)

        # Create signed headers list
        signed_headers = ";".join(sorted(headers.keys(), key=str.lower))

        # Create query string
        query_string = "&".join(
            [
                f"{urllib.parse.quote(k)}={urllib.parse.quote(str(v))}"
                for k, v in sorted(query_params.items())
            ]
        )

        # Create canonical request
        canonical_request = self._create_canonical_request(
            method=method,
            uri=uri,
            query_string=query_string,
            headers=headers,
            signed_headers=signed_headers,
            payload_hash=headers["x-amz-content-sha256"],
        )

        # Create string to sign
        string_to_sign = self._create_string_to_sign(
            timestamp=timestamp,
            date_stamp=date_stamp,
            canonical_request=canonical_request,
        )

        # Calculate signature
        signing_key = self._get_signature_key(date_stamp)
        signature = hmac.new(
            signing_key,
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # Create authorization header
        credential_scope = f"{date_stamp}/{self.region}/{self.service}/aws4_request"
        authorization_header = (
            f"AWS4-HMAC-SHA256 "
            f"Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

        headers["Authorization"] = authorization_header
        return headers

    def create_presigned_url(
        self,
        method: str,
        url: str,
        expires_in: int = 3600,
        query_params: dict[str, str] | None = None,
    ) -> str:
        """Create a presigned URL for S3 operations."""
        if query_params is None:
            query_params = {}

        # Parse URL
        parsed_url = urllib.parse.urlparse(url)

        # Create timestamp
        now = datetime.utcnow()
        timestamp = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        # Add AWS query parameters
        credential_scope = f"{date_stamp}/{self.region}/{self.service}/aws4_request"
        query_params.update(
            {
                "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
                "X-Amz-Credential": f"{self.access_key}/{credential_scope}",
                "X-Amz-Date": timestamp,
                "X-Amz-Expires": str(expires_in),
                "X-Amz-SignedHeaders": "host",
            }
        )

        # Create query string for signing
        query_string = "&".join(
            [
                f"{urllib.parse.quote(k)}={urllib.parse.quote(str(v))}"
                for k, v in sorted(query_params.items())
            ]
        )

        # Create canonical request for presigned URL
        headers = {"host": parsed_url.netloc}
        canonical_request = self._create_canonical_request(
            method=method,
            uri=parsed_url.path or "/",
            query_string=query_string,
            headers=headers,
            signed_headers="host",
            payload_hash="UNSIGNED-PAYLOAD",
        )

        # Create string to sign
        string_to_sign = self._create_string_to_sign(
            timestamp=timestamp,
            date_stamp=date_stamp,
            canonical_request=canonical_request,
        )

        # Calculate signature
        signing_key = self._get_signature_key(date_stamp)
        signature = hmac.new(
            signing_key,
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # Add signature to query parameters
        query_params["X-Amz-Signature"] = signature

        # Build final URL
        final_query_string = "&".join(
            [
                f"{urllib.parse.quote(k)}={urllib.parse.quote(str(v))}"
                for k, v in sorted(query_params.items())
            ]
        )

        return f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?{final_query_string}"
