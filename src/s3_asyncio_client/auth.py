"""AWS Signature Version 4 authentication for S3."""

import datetime as dt
import hashlib
import hmac
import urllib.parse

from yarl import URL


class AWSSignatureV4:
    def __init__(self, access_key: str, secret_key: str, region: str = "us-east-1"):
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region

    def _sha256_hash(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _hmac_sha256(self, key: bytes, data: str) -> bytes:
        return hmac.new(key, data.encode("utf-8"), hashlib.sha256).digest()

    def _get_signature_key(self, date_stamp: str) -> bytes:
        k_date = self._hmac_sha256(f"AWS4{self.secret_key}".encode(), date_stamp)
        k_region = self._hmac_sha256(k_date, self.region)
        k_service = self._hmac_sha256(k_region, "s3")
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
        canonical_uri = urllib.parse.quote(uri, safe="/~")
        canonical_querystring = query_string
        canonical_headers = ""

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
        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{self.region}/s3/aws4_request"
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
        url: URL,
        headers: dict[str, str] | None = None,
        payload: bytes = b"",
        query_params: dict[str, str] | None = None,
    ) -> dict[str, str]:
        assert url.host is not None
        if headers is None:
            headers = {}

        if query_params is None:
            query_params = {}

        now = dt.datetime.now(dt.UTC)
        timestamp = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        headers = headers.copy()
        headers["host"] = url.host
        headers["x-amz-date"] = timestamp

        if "x-amz-content-sha256" not in headers:
            headers["x-amz-content-sha256"] = self._sha256_hash(payload)

        signed_headers = ";".join(sorted([k.lower() for k in headers.keys()]))

        # AWS requires ALL characters to be encoded except unreserved ones
        query_string = "&".join(
            [
                f"{urllib.parse.quote(k, safe='')}="
                f"{urllib.parse.quote(str(v), safe='')}"
                for k, v in sorted(query_params.items())
            ]
        )

        canonical_request = self._create_canonical_request(
            method=method,
            uri=url.path or "/",
            query_string=query_string,
            headers=headers,
            signed_headers=signed_headers,
            payload_hash=headers["x-amz-content-sha256"],
        )

        string_to_sign = self._create_string_to_sign(
            timestamp=timestamp,
            date_stamp=date_stamp,
            canonical_request=canonical_request,
        )

        signing_key = self._get_signature_key(date_stamp)
        signature = hmac.new(
            signing_key,
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        credential_scope = f"{date_stamp}/{self.region}/s3/aws4_request"
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
        url: URL,
        expires_in: int = 3600,
        query_params: dict[str, str] | None = None,
    ) -> str:
        assert url.host is not None
        if query_params is None:
            query_params = {}

        now = dt.datetime.now(dt.UTC)
        timestamp = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        credential_scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        query_params.update(
            {
                "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
                "X-Amz-Credential": f"{self.access_key}/{credential_scope}",
                "X-Amz-Date": timestamp,
                "X-Amz-Expires": str(expires_in),
                "X-Amz-SignedHeaders": "host",
            }
        )

        query_string = "&".join(
            [
                f"{urllib.parse.quote(k, safe='')}="
                f"{urllib.parse.quote(str(v), safe='')}"
                for k, v in sorted(query_params.items())
            ]
        )

        canonical_request = self._create_canonical_request(
            method=method,
            uri=url.path or "/",
            query_string=query_string,
            headers={"host": url.host},
            signed_headers="host",
            payload_hash="UNSIGNED-PAYLOAD",
        )

        string_to_sign = self._create_string_to_sign(
            timestamp=timestamp,
            date_stamp=date_stamp,
            canonical_request=canonical_request,
        )

        signing_key = self._get_signature_key(date_stamp)
        signature = hmac.new(
            signing_key,
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        query_params["X-Amz-Signature"] = signature

        # Use query_params directly with yarl URL to avoid double encoding
        return str(url.with_query(query_params))
