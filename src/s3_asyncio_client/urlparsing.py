import enum
import re

from yarl import URL


class AddressStyle(enum.Enum):
    AUTO = "auto"
    VIRTUAL_HOSTED = "virtual-hosted"
    PATH_STYLE = "path-style"


def get_bucket_url(
    url: URL, bucket: str, address_style: AddressStyle = AddressStyle.AUTO
) -> URL:
    """Constructs a valid bucket URL from the endpoint URL and bucket name.

    If the bucket name is already part of the endpoint URL, it returns the
    endpoint URL as is.
    Otherwise, it constructs a new URL with the bucket name as part of the path
    or as a subdomain, depending on whether the endpoint URL is a valid DNS name.
    """
    bucket = bucket.strip("/")

    if url.scheme != "https" or not url.host:
        raise ValueError("Invalid endpoint URL. Must be a valid HTTPS URL.")
    if url.host.startswith(bucket + ".") and url.path.endswith(bucket):
        raise ValueError(
            f"Bucket '{bucket}' is both in the host and path part of the URL '{url}'. "
        )

    is_valid_host = is_valid_s3_bucket_subdomain(bucket)

    # new AWS S3 buckets, Backblaze B2, DigitalOcean Spaces, etc.
    virtual_hosted_style = (
        url
        if url.host.startswith(bucket + ".")
        else url.with_host(f"{bucket}.{url.host}")
    )
    #  old AWS S3 buckets or MinIO
    path_style = url.with_path(bucket)

    match address_style:
        case AddressStyle.AUTO:
            return virtual_hosted_style if is_valid_host else path_style
        case AddressStyle.VIRTUAL_HOSTED:
            if is_valid_host:
                return virtual_hosted_style
        case AddressStyle.PATH_STYLE:
            return path_style

    raise ValueError(f"Invalid bucket name '{bucket}' for endpoint URL '{url}'")


def is_valid_s3_bucket_subdomain(bucket: str) -> bool:
    """S3-specific subdomain validation (stricter than general DNS)."""
    if not bucket or len(bucket) < 3 or len(bucket) > 63:
        return False

    if not re.match(r"^[a-z0-9.-]+$", bucket):
        return False

    if bucket[0] in "-." or bucket[-1] in "-.":
        return False

    if ".." in bucket or ".-" in bucket or "-." in bucket:
        return False

    # Cannot look like IP address
    if re.match(r"^\d+\.\d+\.\d+\.\d+$", bucket):
        return False

    return True
