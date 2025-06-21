import xml.etree.ElementTree as ET

from s3_asyncio_client.buckets import _build_create_bucket_xml

NS = "http://s3.amazonaws.com/doc/2006-03-01/"


class TestBuildCreateBucketXml:
    def test_no_configuration_returns_none(self):
        result = _build_create_bucket_xml()
        assert result is None

    def test_us_east_1_returns_none(self):
        result = _build_create_bucket_xml(region="us-east-1")
        assert result is None

    def test_region_only(self):
        result = _build_create_bucket_xml(region="eu-west-1")

        assert result is not None
        assert isinstance(result, bytes)

        root = ET.fromstring(result)
        assert root.tag == f"{{{NS}}}CreateBucketConfiguration"

        location_constraint = root.find(f"{{{NS}}}LocationConstraint")
        assert location_constraint is not None
        assert location_constraint.text == "eu-west-1"

    def test_location_type_and_name(self):
        result = _build_create_bucket_xml(
            location_type="AvailabilityZone", location_name="us-west-2a"
        )

        assert result is not None
        root = ET.fromstring(result)

        location = root.find(f"{{{NS}}}Location")
        assert location is not None

        name = location.find(f"{{{NS}}}Name")
        assert name is not None
        assert name.text == "us-west-2a"

        type_elem = location.find(f"{{{NS}}}Type")
        assert type_elem is not None
        assert type_elem.text == "AvailabilityZone"

    def test_location_name_only(self):
        result = _build_create_bucket_xml(location_name="us-west-2a")

        assert result is not None
        root = ET.fromstring(result)

        location = root.find(f"{{{NS}}}Location")
        assert location is not None

        name = location.find(f"{{{NS}}}Name")
        assert name is not None
        assert name.text == "us-west-2a"

        type_elem = location.find(f"{{{NS}}}Type")
        assert type_elem is None

    def test_location_type_only(self):
        result = _build_create_bucket_xml(location_type="AvailabilityZone")

        assert result is not None
        root = ET.fromstring(result)

        location = root.find(f"{{{NS}}}Location")
        assert location is not None

        type_elem = location.find(f"{{{NS}}}Type")
        assert type_elem is not None
        assert type_elem.text == "AvailabilityZone"

        name = location.find(f"{{{NS}}}Name")
        assert name is None

    def test_bucket_type_and_data_redundancy(self):
        result = _build_create_bucket_xml(
            bucket_type="Directory", data_redundancy="SingleAvailabilityZone"
        )

        assert result is not None
        root = ET.fromstring(result)

        bucket = root.find(f"{{{NS}}}Bucket")
        assert bucket is not None

        data_redundancy = bucket.find(f"{{{NS}}}DataRedundancy")
        assert data_redundancy is not None
        assert data_redundancy.text == "SingleAvailabilityZone"

        type_elem = bucket.find(f"{{{NS}}}Type")
        assert type_elem is not None
        assert type_elem.text == "Directory"

    def test_bucket_type_only(self):
        result = _build_create_bucket_xml(bucket_type="Directory")

        assert result is not None
        root = ET.fromstring(result)

        bucket = root.find(f"{{{NS}}}Bucket")
        assert bucket is not None

        type_elem = bucket.find(f"{{{NS}}}Type")
        assert type_elem is not None
        assert type_elem.text == "Directory"

        data_redundancy = bucket.find(f"{{{NS}}}DataRedundancy")
        assert data_redundancy is None

    def test_data_redundancy_only(self):
        result = _build_create_bucket_xml(data_redundancy="SingleAvailabilityZone")

        assert result is not None
        root = ET.fromstring(result)

        bucket = root.find(f"{{{NS}}}Bucket")
        assert bucket is not None

        data_redundancy = bucket.find(f"{{{NS}}}DataRedundancy")
        assert data_redundancy is not None
        assert data_redundancy.text == "SingleAvailabilityZone"

        type_elem = bucket.find(f"{{{NS}}}Type")
        assert type_elem is None

    def test_all_parameters(self):
        """Test XML generation with all parameters."""
        result = _build_create_bucket_xml(
            region="eu-west-1",
            location_type="AvailabilityZone",
            location_name="eu-west-1a",
            bucket_type="Directory",
            data_redundancy="SingleAvailabilityZone",
        )

        assert result is not None
        root = ET.fromstring(result)
        assert root.tag == f"{{{NS}}}CreateBucketConfiguration"

        location_constraint = root.find(f"{{{NS}}}LocationConstraint")
        assert location_constraint is not None
        assert location_constraint.text == "eu-west-1"

        location = root.find(f"{{{NS}}}Location")
        assert location is not None

        name = location.find(f"{{{NS}}}Name")
        assert name is not None
        assert name.text == "eu-west-1a"

        location_type = location.find(f"{{{NS}}}Type")
        assert location_type is not None
        assert location_type.text == "AvailabilityZone"

        bucket = root.find(f"{{{NS}}}Bucket")
        assert bucket is not None

        data_redundancy = bucket.find(f"{{{NS}}}DataRedundancy")
        assert data_redundancy is not None
        assert data_redundancy.text == "SingleAvailabilityZone"

        bucket_type = bucket.find(f"{{{NS}}}Type")
        assert bucket_type is not None
        assert bucket_type.text == "Directory"

    def test_xml_declaration_and_encoding(self):
        result = _build_create_bucket_xml(region="eu-west-1")

        assert result is not None
        assert result.startswith(b"<?xml version='1.0' encoding='utf-8'?>")

        xml_str = result.decode("utf-8")
        assert "CreateBucketConfiguration" in xml_str

    def test_xml_namespace(self):
        result = _build_create_bucket_xml(region="eu-west-1")

        assert result is not None
        root = ET.fromstring(result)
        # Namespace is included in tag name, not as attribute in parsed XML
        assert NS in root.tag
