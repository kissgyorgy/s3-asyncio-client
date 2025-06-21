"""Tests for multipart XML generation utilities."""

import xml.etree.ElementTree as ET

from s3_asyncio_client.multipart import _build_complete_multipart_xml


class TestBuildCompleteMultipartXml:
    """Tests for _build_complete_multipart_xml function."""

    def test_single_part(self):
        """Test XML generation with single part."""
        parts = [{"part_number": 1, "etag": "abcd1234"}]

        result = _build_complete_multipart_xml(parts)

        assert isinstance(result, bytes)
        root = ET.fromstring(result)

        assert root.tag == "CompleteMultipartUpload"

        part_elems = root.findall("Part")
        assert len(part_elems) == 1

        part = part_elems[0]
        part_number = part.find("PartNumber")
        etag = part.find("ETag")

        assert part_number is not None
        assert part_number.text == "1"
        assert etag is not None
        assert etag.text == '"abcd1234"'

    def test_multiple_parts(self):
        """Test XML generation with multiple parts."""
        parts = [
            {"part_number": 1, "etag": "part1etag"},
            {"part_number": 2, "etag": "part2etag"},
            {"part_number": 3, "etag": "part3etag"},
        ]

        result = _build_complete_multipart_xml(parts)

        root = ET.fromstring(result)
        assert root.tag == "CompleteMultipartUpload"

        part_elems = root.findall("Part")
        assert len(part_elems) == 3

        # Check each part
        for i, part_elem in enumerate(part_elems, 1):
            part_number = part_elem.find("PartNumber")
            etag = part_elem.find("ETag")

            assert part_number is not None
            assert part_number.text == str(i)
            assert etag is not None
            assert etag.text == f'"part{i}etag"'

    def test_parts_sorted_by_part_number(self):
        """Test that parts are sorted by part_number."""
        parts = [
            {"part_number": 3, "etag": "etag3"},
            {"part_number": 1, "etag": "etag1"},
            {"part_number": 2, "etag": "etag2"},
        ]

        result = _build_complete_multipart_xml(parts)

        root = ET.fromstring(result)
        part_elems = root.findall("Part")

        # Should be sorted 1, 2, 3
        expected_order = ["1", "2", "3"]
        expected_etags = ['"etag1"', '"etag2"', '"etag3"']

        for i, part_elem in enumerate(part_elems):
            part_number = part_elem.find("PartNumber")
            etag = part_elem.find("ETag")

            assert part_number is not None
            assert part_number.text == expected_order[i]
            assert etag is not None
            assert etag.text == expected_etags[i]

    def test_etag_formatting(self):
        """Test that ETags are properly quoted."""
        parts = [
            {"part_number": 1, "etag": "unquoted-etag"},
            {"part_number": 2, "etag": "another-etag"},
        ]

        result = _build_complete_multipart_xml(parts)

        root = ET.fromstring(result)
        part_elems = root.findall("Part")

        for part_elem in part_elems:
            etag = part_elem.find("ETag")
            assert etag is not None
            # Should be wrapped in double quotes
            assert etag.text.startswith('"')
            assert etag.text.endswith('"')

    def test_xml_structure(self):
        """Test overall XML structure."""
        parts = [{"part_number": 1, "etag": "test-etag"}]

        result = _build_complete_multipart_xml(parts)

        # Should be valid XML
        root = ET.fromstring(result)

        # Root element
        assert root.tag == "CompleteMultipartUpload"

        # Should have exactly one Part child
        part_children = root.findall("Part")
        assert len(part_children) == 1

        # Part should have PartNumber and ETag children
        part = part_children[0]
        part_number = part.find("PartNumber")
        etag = part.find("ETag")

        assert part_number is not None
        assert etag is not None

        # Should have no other children
        assert len(list(part)) == 2

    def test_large_part_numbers(self):
        """Test with large part numbers."""
        parts = [
            {"part_number": 9999, "etag": "etag9999"},
            {"part_number": 10000, "etag": "etag10000"},
        ]

        result = _build_complete_multipart_xml(parts)

        root = ET.fromstring(result)
        part_elems = root.findall("Part")

        assert len(part_elems) == 2

        # First part (sorted order)
        part1 = part_elems[0]
        part_number1 = part1.find("PartNumber")
        assert part_number1 is not None
        assert part_number1.text == "9999"

        # Second part
        part2 = part_elems[1]
        part_number2 = part2.find("PartNumber")
        assert part_number2 is not None
        assert part_number2.text == "10000"

    def test_utf8_encoding(self):
        """Test that result is properly UTF-8 encoded."""
        parts = [{"part_number": 1, "etag": "test-etag"}]

        result = _build_complete_multipart_xml(parts)

        # Should be bytes
        assert isinstance(result, bytes)

        # Should be decodable as UTF-8
        xml_str = result.decode("utf-8")
        assert "CompleteMultipartUpload" in xml_str
        assert "PartNumber" in xml_str
        assert "ETag" in xml_str

    def test_special_characters_in_etag(self):
        """Test handling of special characters in ETags."""
        parts = [{"part_number": 1, "etag": "etag-with-special-chars-123"}]

        result = _build_complete_multipart_xml(parts)

        root = ET.fromstring(result)
        part = root.find("Part")
        assert part is not None

        etag = part.find("ETag")
        assert etag is not None
        assert etag.text == '"etag-with-special-chars-123"'
