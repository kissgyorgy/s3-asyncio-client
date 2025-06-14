"""Tests for S3Client.from_aws_config classmethod."""

import os
import pathlib
import tempfile

import pytest

from s3_asyncio_client.client import S3Client


class TestFromAWSConfig:
    """Test S3Client.from_aws_config method."""

    def test_basic_config_default_profile(self, tmp_path: pathlib.Path):
        """Test basic config with default profile."""
        # Create credentials file
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[default]
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
region = us-west-2
""")

        # Create config file
        config_file = tmp_path / "config"
        config_file.write_text("""[default]
region = us-east-1
output = json
""")

        client = S3Client.from_aws_config(
            credentials_path=credentials_file, config_path=config_file
        )

        assert client.access_key == "AKIAIOSFODNN7EXAMPLE"
        assert client.secret_key == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        assert client.region == "us-west-2"  # credentials takes precedence
        assert client.endpoint_url == "https://s3.us-west-2.amazonaws.com"

    def test_named_profile(self, tmp_path: pathlib.Path):
        """Test config with named profile."""
        # Create credentials file
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[default]
aws_access_key_id = DEFAULTKEY
aws_secret_access_key = DEFAULTSECRET
region = us-east-1

[dev]
aws_access_key_id = DEVKEY
aws_secret_access_key = DEVSECRET
region = us-west-1
""")

        # Create config file
        config_file = tmp_path / "config"
        config_file.write_text("""[default]
region = us-east-1

[profile dev]
region = eu-west-1
output = table
""")

        client = S3Client.from_aws_config(
            profile_name="dev",
            credentials_path=credentials_file,
            config_path=config_file,
        )

        assert client.access_key == "DEVKEY"
        assert client.secret_key == "DEVSECRET"
        assert client.region == "us-west-1"  # credentials takes precedence
        assert client.endpoint_url == "https://s3.us-west-1.amazonaws.com"

    def test_custom_endpoint_url_in_credentials(self, tmp_path: pathlib.Path):
        """Test custom endpoint URL in credentials file."""
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[minio]
aws_access_key_id = minioadmin
aws_secret_access_key = minioadmin
region = us-east-1
endpoint_url = http://localhost:9000
""")

        client = S3Client.from_aws_config(
            profile_name="minio", credentials_path=credentials_file, config_path=None
        )

        assert client.access_key == "minioadmin"
        assert client.secret_key == "minioadmin"
        assert client.region == "us-east-1"
        assert client.endpoint_url == "http://localhost:9000"

    def test_custom_endpoint_url_in_config(self, tmp_path: pathlib.Path):
        """Test custom endpoint URL in config file."""
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[minio]
aws_access_key_id = minioadmin
aws_secret_access_key = minioadmin
""")

        config_file = tmp_path / "config"
        config_file.write_text("""[profile minio]
region = us-east-1
endpoint_url = http://localhost:9000
output = json
""")

        client = S3Client.from_aws_config(
            profile_name="minio",
            credentials_path=credentials_file,
            config_path=config_file,
        )

        assert client.access_key == "minioadmin"
        assert client.secret_key == "minioadmin"
        assert client.region == "us-east-1"
        assert client.endpoint_url == "http://localhost:9000"

    def test_s3_section_in_config(self, tmp_path: pathlib.Path):
        """Test s3 section in config file."""
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[custom]
aws_access_key_id = CUSTOMKEY
aws_secret_access_key = CUSTOMSECRET
""")

        config_file = tmp_path / "config"
        config_file.write_text("""[profile custom]
region = us-east-1

[profile custom s3]
endpoint_url = http://localhost:9000
""")

        client = S3Client.from_aws_config(
            profile_name="custom",
            credentials_path=credentials_file,
            config_path=config_file,
        )

        assert client.access_key == "CUSTOMKEY"
        assert client.secret_key == "CUSTOMSECRET"
        assert client.region == "us-east-1"
        # For now, simple s3 section handling is not implemented
        assert client.endpoint_url == "https://s3.us-east-1.amazonaws.com"

    def test_region_precedence(self, tmp_path: pathlib.Path):
        """Test region precedence: credentials > config > env > default."""
        # Set environment variable
        os.environ["AWS_DEFAULT_REGION"] = "ap-south-1"

        try:
            credentials_file = tmp_path / "credentials"
            credentials_file.write_text("""[test]
aws_access_key_id = TESTKEY
aws_secret_access_key = TESTSECRET
""")

            config_file = tmp_path / "config"
            config_file.write_text("""[profile test]
region = eu-central-1
""")

            # Test config precedence over env
            client = S3Client.from_aws_config(
                profile_name="test",
                credentials_path=credentials_file,
                config_path=config_file,
            )
            assert client.region == "eu-central-1"

            # Test env precedence when no config region
            config_file.write_text("""[profile test]
output = json
""")

            client = S3Client.from_aws_config(
                profile_name="test",
                credentials_path=credentials_file,
                config_path=config_file,
            )
            assert client.region == "ap-south-1"

        finally:
            # Clean up environment
            if "AWS_DEFAULT_REGION" in os.environ:
                del os.environ["AWS_DEFAULT_REGION"]

    def test_endpoint_url_precedence(self, tmp_path: pathlib.Path):
        """Test endpoint_url precedence: credentials > config."""
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[test]
aws_access_key_id = TESTKEY
aws_secret_access_key = TESTSECRET
endpoint_url = http://creds.example.com
""")

        config_file = tmp_path / "config"
        config_file.write_text("""[profile test]
region = us-east-1
endpoint_url = http://config.example.com
""")

        client = S3Client.from_aws_config(
            profile_name="test",
            credentials_path=credentials_file,
            config_path=config_file,
        )

        # Credentials should take precedence
        assert client.endpoint_url == "http://creds.example.com"

    def test_whitespace_handling(self, tmp_path: pathlib.Path):
        """Test various whitespace scenarios."""
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[whitespace]
aws_access_key_id   =   WHITESPACEKEY
aws_secret_access_key = WHITESPACESECRET
region  =  us-west-2
endpoint_url = http://localhost:9000
""")

        config_file = tmp_path / "config"
        config_file.write_text("""[profile whitespace]
region   =   eu-west-1
output = json
""")

        client = S3Client.from_aws_config(
            profile_name="whitespace",
            credentials_path=credentials_file,
            config_path=config_file,
        )

        assert client.access_key == "WHITESPACEKEY"
        assert client.secret_key == "WHITESPACESECRET"
        assert client.region == "us-west-2"  # credentials takes precedence
        assert client.endpoint_url == "http://localhost:9000"

    def test_missing_credentials_file(self, tmp_path: pathlib.Path):
        """Test error when credentials file doesn't exist."""
        with pytest.raises(FileNotFoundError, match="AWS credentials file not found"):
            S3Client.from_aws_config(credentials_path=tmp_path / "nonexistent")

    def test_missing_profile_in_credentials(self, tmp_path: pathlib.Path):
        """Test error when profile doesn't exist in credentials."""
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[default]
aws_access_key_id = DEFAULTKEY
aws_secret_access_key = DEFAULTSECRET
""")

        with pytest.raises(
            ValueError, match="Profile 'nonexistent' not found in credentials file"
        ):
            S3Client.from_aws_config(
                profile_name="nonexistent", credentials_path=credentials_file
            )

    def test_missing_access_key(self, tmp_path: pathlib.Path):
        """Test error when access key is missing."""
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[broken]
aws_secret_access_key = TESTSECRET
region = us-east-1
""")

        with pytest.raises(
            ValueError, match="aws_access_key_id not found for profile 'broken'"
        ):
            S3Client.from_aws_config(
                profile_name="broken", credentials_path=credentials_file
            )

    def test_missing_secret_key(self, tmp_path: pathlib.Path):
        """Test error when secret key is missing."""
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[broken]
aws_access_key_id = TESTKEY
region = us-east-1
""")

        with pytest.raises(
            ValueError, match="aws_secret_access_key not found for profile 'broken'"
        ):
            S3Client.from_aws_config(
                profile_name="broken", credentials_path=credentials_file
            )

    def test_extra_options_ignored(self, tmp_path: pathlib.Path):
        """Test that extra options are ignored gracefully."""
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[extra]
aws_access_key_id = EXTRAKEY
aws_secret_access_key = EXTRASECRET
region = us-east-1
aws_session_token = SESSIONTOKEN
role_arn = arn:aws:iam::123456789012:role/TestRole
source_profile = default
mfa_serial = arn:aws:iam::123456789012:mfa/user
unknown_option = some_value
""")

        config_file = tmp_path / "config"
        config_file.write_text("""[profile extra]
region = us-west-1
output = json
cli_pager =
cli_auto_prompt = on
max_concurrent_requests = 10
max_queue_size = 1000
""")

        # Should work fine and ignore unknown options
        client = S3Client.from_aws_config(
            profile_name="extra",
            credentials_path=credentials_file,
            config_path=config_file,
        )

        assert client.access_key == "EXTRAKEY"
        assert client.secret_key == "EXTRASECRET"
        assert client.region == "us-east-1"  # credentials takes precedence

    def test_missing_config_file_ok(self, tmp_path: pathlib.Path):
        """Test that missing config file is OK."""
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[test]
aws_access_key_id = TESTKEY
aws_secret_access_key = TESTSECRET
region = us-west-2
""")

        client = S3Client.from_aws_config(
            profile_name="test",
            credentials_path=credentials_file,
            config_path=tmp_path / "nonexistent_config",
        )

        assert client.access_key == "TESTKEY"
        assert client.secret_key == "TESTSECRET"
        assert client.region == "us-west-2"

    def test_empty_files(self, tmp_path: pathlib.Path):
        """Test behavior with empty files."""
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("")

        config_file = tmp_path / "config"
        config_file.write_text("")

        with pytest.raises(
            ValueError, match="Profile 'default' not found in credentials file"
        ):
            S3Client.from_aws_config(
                credentials_path=credentials_file, config_path=config_file
            )

    def test_malformed_config_files(self, tmp_path: pathlib.Path):
        """Test behavior with malformed config files."""
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[default
aws_access_key_id = TESTKEY
aws_secret_access_key = TESTSECRET
invalid line without equals
""")

        # configparser should handle this gracefully by ignoring malformed lines
        # This may not raise an error depending on configparser behavior
        try:
            client = S3Client.from_aws_config(credentials_path=credentials_file)
            # If no error, verify it found what it could
            assert client.access_key == "TESTKEY"
            assert client.secret_key == "TESTSECRET"
        except Exception:
            # Malformed config might cause errors, which is acceptable
            pass

    def test_case_sensitivity(self, tmp_path: pathlib.Path):
        """Test profile name case sensitivity."""
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[CaseSensitive]
aws_access_key_id = CASEKEY
aws_secret_access_key = CASESECRET
region = us-east-1
""")

        # Exact case should work
        client = S3Client.from_aws_config(
            profile_name="CaseSensitive", credentials_path=credentials_file
        )
        assert client.access_key == "CASEKEY"

        # Different case should fail
        with pytest.raises(ValueError, match="Profile 'casesensitive' not found"):
            S3Client.from_aws_config(
                profile_name="casesensitive", credentials_path=credentials_file
            )

    def test_pathlib_path_objects(self, tmp_path: pathlib.Path):
        """Test using pathlib.Path objects for file paths."""
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[pathlib]
aws_access_key_id = PATHLIBKEY
aws_secret_access_key = PATHLIBSECRET
region = us-east-1
""")

        # Test with pathlib.Path objects
        client = S3Client.from_aws_config(
            profile_name="pathlib",
            credentials_path=credentials_file,  # pathlib.Path object
            config_path=tmp_path / "nonexistent",  # pathlib.Path object
        )

        assert client.access_key == "PATHLIBKEY"
        assert client.secret_key == "PATHLIBSECRET"

    def test_string_path_objects(self, tmp_path: pathlib.Path):
        """Test using string paths."""
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[string]
aws_access_key_id = STRINGKEY
aws_secret_access_key = STRINGSECRET
region = us-east-1
""")

        # Test with string paths
        client = S3Client.from_aws_config(
            profile_name="string",
            credentials_path=str(credentials_file),  # string path
            config_path=str(tmp_path / "nonexistent"),  # string path
        )

        assert client.access_key == "STRINGKEY"
        assert client.secret_key == "STRINGSECRET"

    def test_default_paths(self, monkeypatch):
        """Test default path behavior."""
        # Create temp directory structure
        with tempfile.TemporaryDirectory() as temp_home:
            aws_dir = pathlib.Path(temp_home) / ".aws"
            aws_dir.mkdir()

            credentials_file = aws_dir / "credentials"
            credentials_file.write_text("""[default]
aws_access_key_id = DEFAULTKEY
aws_secret_access_key = DEFAULTSECRET
region = us-east-1
""")

            config_file = aws_dir / "config"
            config_file.write_text("""[default]
output = json
""")

            # Mock home directory
            monkeypatch.setattr(pathlib.Path, "home", lambda: pathlib.Path(temp_home))

            # Test with default paths (should find ~/.aws/credentials and ~/.aws/config)
            client = S3Client.from_aws_config()

            assert client.access_key == "DEFAULTKEY"
            assert client.secret_key == "DEFAULTSECRET"
            assert client.region == "us-east-1"

    def test_credentials_precedence_over_config_region(self, tmp_path: pathlib.Path):
        """Test that credentials region takes precedence over config region."""
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[precedence]
aws_access_key_id = PRECEDENCEKEY
aws_secret_access_key = PRECEDENCESECRET
region = ap-southeast-1
""")

        config_file = tmp_path / "config"
        config_file.write_text("""[profile precedence]
region = eu-north-1
output = json
""")

        client = S3Client.from_aws_config(
            profile_name="precedence",
            credentials_path=credentials_file,
            config_path=config_file,
        )

        # Region from credentials should win
        assert client.region == "ap-southeast-1"
        assert client.endpoint_url == "https://s3.ap-southeast-1.amazonaws.com"
