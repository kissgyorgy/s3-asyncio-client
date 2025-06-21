import xml.etree.ElementTree as ET
from typing import Any

from .base import _S3ClientBase


def _build_create_bucket_xml(
    region: str | None = None,
    location_type: str | None = None,
    location_name: str | None = None,
    bucket_type: str | None = None,
    data_redundancy: str | None = None,
) -> bytes | None:
    if not (
        region
        and region != "us-east-1"
        or location_type
        or location_name
        or bucket_type
        or data_redundancy
    ):
        return None

    root = ET.Element("CreateBucketConfiguration")
    root.set("xmlns", "http://s3.amazonaws.com/doc/2006-03-01/")

    if region and region != "us-east-1":
        location_constraint = ET.SubElement(root, "LocationConstraint")
        location_constraint.text = region

    # Location for directory buckets
    if location_type or location_name:
        location = ET.SubElement(root, "Location")
        if location_name:
            name = ET.SubElement(location, "Name")
            name.text = location_name
        if location_type:
            type_elem = ET.SubElement(location, "Type")
            type_elem.text = location_type

    # Bucket configuration for directory buckets
    if bucket_type or data_redundancy:
        bucket = ET.SubElement(root, "Bucket")
        if data_redundancy:
            data_redundancy_elem = ET.SubElement(bucket, "DataRedundancy")
            data_redundancy_elem.text = data_redundancy
        if bucket_type:
            type_elem = ET.SubElement(bucket, "Type")
            type_elem.text = bucket_type

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


class _BucketOperations(_S3ClientBase):
    # https://docs.aws.amazon.com/AmazonS3/latest/API/API_CreateBucket.html
    async def create_bucket(
        self,
        region: str | None = None,
        acl: str | None = None,
        grant_full_control: str | None = None,
        grant_read: str | None = None,
        grant_read_acp: str | None = None,
        grant_write: str | None = None,
        grant_write_acp: str | None = None,
        object_lock_enabled: bool | None = None,
        object_ownership: str | None = None,
        location_type: str | None = None,
        location_name: str | None = None,
        bucket_type: str | None = None,
        data_redundancy: str | None = None,
    ) -> dict[str, Any]:
        headers = {}
        data = None

        if acl:
            headers["x-amz-acl"] = acl
        if grant_full_control:
            headers["x-amz-grant-full-control"] = grant_full_control
        if grant_read:
            headers["x-amz-grant-read"] = grant_read
        if grant_read_acp:
            headers["x-amz-grant-read-acp"] = grant_read_acp
        if grant_write:
            headers["x-amz-grant-write"] = grant_write
        if grant_write_acp:
            headers["x-amz-grant-write-acp"] = grant_write_acp
        if object_lock_enabled is not None:
            headers["x-amz-bucket-object-lock-enabled"] = str(
                object_lock_enabled
            ).lower()
        if object_ownership:
            headers["x-amz-object-ownership"] = object_ownership

        data = _build_create_bucket_xml(
            region=region,
            location_type=location_type,
            location_name=location_name,
            bucket_type=bucket_type,
            data_redundancy=data_redundancy,
        )
        if data:
            headers["Content-Type"] = "application/xml"

        response = await self._make_request(
            "PUT", key=None, headers=headers if headers else None, data=data
        )

        result = {
            "location": response.headers.get("Location"),
        }

        response.close()
        return result

    async def delete_bucket(self) -> dict[str, Any]:
        response = await self._make_request("DELETE", key=None)
        response.close()
        return {}

    async def list_objects(
        self,
        prefix: str | None = None,
        max_keys: int = 1000,
        continuation_token: str | None = None,
    ) -> dict[str, Any]:
        params = {
            "list-type": "2",  # Use ListObjectsV2
            "max-keys": str(max_keys),
        }

        if prefix:
            # OVH S3 service requires leading slash in prefix
            # but returns normalized keys
            if "ovh.net" in str(self.bucket_url) and not prefix.startswith("/"):
                params["prefix"] = "/" + prefix
            else:
                params["prefix"] = prefix

        if continuation_token:
            params["continuation-token"] = continuation_token

        response = await self._make_request("GET", params=params)

        response_text = await response.text()
        response.close()

        # Handle empty response (some S3 services return empty response
        # for empty buckets)
        if not response_text.strip():
            return {
                "objects": [],
                "is_truncated": False,
                "next_continuation_token": None,
                "prefix": prefix,
                "max_keys": max_keys,
            }

        try:
            root = ET.fromstring(response_text)
        except ET.ParseError as e:
            raise ValueError(
                f"Invalid XML response from S3 service: {e}. "
                f"Response: {response_text[:200]}..."
            )

        objects = []
        for content in root.findall(
            ".//{http://s3.amazonaws.com/doc/2006-03-01/}Contents"
        ):
            key = content.find(".//{http://s3.amazonaws.com/doc/2006-03-01/}Key")
            last_modified = content.find(
                ".//{http://s3.amazonaws.com/doc/2006-03-01/}LastModified"
            )
            etag = content.find(".//{http://s3.amazonaws.com/doc/2006-03-01/}ETag")
            size = content.find(".//{http://s3.amazonaws.com/doc/2006-03-01/}Size")
            storage_class = content.find(
                ".//{http://s3.amazonaws.com/doc/2006-03-01/}StorageClass"
            )

            key_text = key.text if key is not None else ""
            # Normalize key by removing leading slash if present (for OVH compatibility)
            if key_text.startswith("/"):
                key_text = key_text[1:]

            obj = {
                "key": key_text,
                "last_modified": (
                    last_modified.text if last_modified is not None else ""
                ),
                "etag": etag.text.strip('"') if etag is not None else "",
                "size": int(size.text) if size is not None else 0,
                "storage_class": (
                    storage_class.text if storage_class is not None else "STANDARD"
                ),
            }
            objects.append(obj)

        # Extract pagination info
        is_truncated_elem = root.find(
            ".//{http://s3.amazonaws.com/doc/2006-03-01/}IsTruncated"
        )
        next_token_elem = root.find(
            ".//{http://s3.amazonaws.com/doc/2006-03-01/}NextContinuationToken"
        )

        is_truncated = (
            is_truncated_elem is not None and is_truncated_elem.text == "true"
        )
        next_continuation_token = (
            next_token_elem.text if next_token_elem is not None else None
        )

        result = {
            "objects": objects,
            "is_truncated": is_truncated,
            "next_continuation_token": next_continuation_token,
            "prefix": prefix,
            "max_keys": max_keys,
        }

        return result
