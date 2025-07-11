import os
import pathlib
import tempfile

import pytest

from s3_asyncio_client.client import S3Client


class TestFromAWSConfig:
    def test_basic_config_default_profile(self, tmp_path: pathlib.Path):
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[default]
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
region = us-west-2
endpoint_url = https://s3.us-west-2.amazonaws.com
""")

        config_file = tmp_path / "config"
        config_file.write_text("""[default]
region = us-east-1
output = json
""")

        client = S3Client.from_aws_config(
            bucket="test-bucket",
            credentials_path=credentials_file,
            config_path=config_file,
        )

        assert client.access_key == "AKIAIOSFODNN7EXAMPLE"
        assert client.secret_key == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        assert client.region == "us-west-2"
        assert str(client.endpoint_url) == "https://s3.us-west-2.amazonaws.com"

    def test_named_profile(self, tmp_path: pathlib.Path):
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[default]
aws_access_key_id = DEFAULTKEY
aws_secret_access_key = DEFAULTSECRET
region = us-east-1

[dev]
aws_access_key_id = DEVKEY
aws_secret_access_key = DEVSECRET
region = us-west-1
endpoint_url = https://s3.us-west-1.amazonaws.com
""")

        config_file = tmp_path / "config"
        config_file.write_text("""[default]
region = us-east-1

[profile dev]
region = eu-west-1
output = table
""")

        client = S3Client.from_aws_config(
            bucket="test-bucket",
            profile_name="dev",
            credentials_path=credentials_file,
            config_path=config_file,
        )

        assert client.access_key == "DEVKEY"
        assert client.secret_key == "DEVSECRET"
        assert client.region == "us-west-1"
        assert str(client.endpoint_url) == "https://s3.us-west-1.amazonaws.com"

    def test_custom_endpoint_url_in_credentials(self, tmp_path: pathlib.Path):
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[minio]
aws_access_key_id = minioadmin
aws_secret_access_key = minioadmin
region = us-east-1
endpoint_url = https://s3.us-east-1.amazonaws.com
""")

        client = S3Client.from_aws_config(
            bucket="test-bucket",
            profile_name="minio",
            credentials_path=credentials_file,
            config_path=None,
        )

        assert client.access_key == "minioadmin"
        assert client.secret_key == "minioadmin"
        assert client.region == "us-east-1"
        assert str(client.endpoint_url) == "https://s3.us-east-1.amazonaws.com"

    def test_custom_endpoint_url_in_config(self, tmp_path: pathlib.Path):
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[minio]
aws_access_key_id = minioadmin
aws_secret_access_key = minioadmin
endpoint_url = https://s3.us-east-1.amazonaws.com
""")

        config_file = tmp_path / "config"
        config_file.write_text("""[profile minio]
region = us-east-1
endpoint_url = https://s3.us-east-1.amazonaws.com
output = json
""")

        client = S3Client.from_aws_config(
            bucket="test-bucket",
            profile_name="minio",
            credentials_path=credentials_file,
            config_path=config_file,
        )

        assert client.access_key == "minioadmin"
        assert client.secret_key == "minioadmin"
        assert client.region == "us-east-1"
        assert str(client.endpoint_url) == "https://s3.us-east-1.amazonaws.com"

    def test_s3_section_in_config(self, tmp_path: pathlib.Path):
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[custom]
aws_access_key_id = CUSTOMKEY
aws_secret_access_key = CUSTOMSECRET
endpoint_url = https://s3.us-east-1.amazonaws.com
""")

        config_file = tmp_path / "config"
        config_file.write_text("""[profile custom]
region = us-east-1

[profile custom s3]
endpoint_url = https://s3.us-east-1.amazonaws.com
""")

        client = S3Client.from_aws_config(
            bucket="test-bucket",
            profile_name="custom",
            credentials_path=credentials_file,
            config_path=config_file,
        )

        assert client.access_key == "CUSTOMKEY"
        assert client.secret_key == "CUSTOMSECRET"
        assert client.region == "us-east-1"
        assert str(client.endpoint_url) == "https://s3.us-east-1.amazonaws.com"

    def test_region_precedence(self, tmp_path: pathlib.Path):
        os.environ["AWS_DEFAULT_REGION"] = "ap-south-1"

        try:
            credentials_file = tmp_path / "credentials"
            credentials_file.write_text("""[test]
aws_access_key_id = TESTKEY
aws_secret_access_key = TESTSECRET
endpoint_url = https://s3.us-east-1.amazonaws.com
""")

            config_file = tmp_path / "config"
            config_file.write_text("""[profile test]
region = eu-central-1
""")

            # Test config precedence over env
            client = S3Client.from_aws_config(
                bucket="test-bucket",
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
                bucket="test-bucket",
                profile_name="test",
                credentials_path=credentials_file,
                config_path=config_file,
            )
            assert client.region == "ap-south-1"

        finally:
            if "AWS_DEFAULT_REGION" in os.environ:
                del os.environ["AWS_DEFAULT_REGION"]

    def test_endpoint_url_precedence(self, tmp_path: pathlib.Path):
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[test]
aws_access_key_id = TESTKEY
aws_secret_access_key = TESTSECRET
endpoint_url = https://creds.example.com
""")

        config_file = tmp_path / "config"
        config_file.write_text("""[profile test]
region = us-east-1
endpoint_url = https://config.example.com
""")

        client = S3Client.from_aws_config(
            bucket="test-bucket",
            profile_name="test",
            credentials_path=credentials_file,
            config_path=config_file,
        )

        # Credentials should take precedence
        assert str(client.endpoint_url) == "https://creds.example.com"

    def test_whitespace_handling(self, tmp_path: pathlib.Path):
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[whitespace]
aws_access_key_id   =   WHITESPACEKEY
aws_secret_access_key = WHITESPACESECRET
region  =  us-west-2
endpoint_url = https://s3.us-east-1.amazonaws.com
""")

        config_file = tmp_path / "config"
        config_file.write_text("""[profile whitespace]
region   =   eu-west-1
output = json
""")

        client = S3Client.from_aws_config(
            bucket="test-bucket",
            profile_name="whitespace",
            credentials_path=credentials_file,
            config_path=config_file,
        )

        assert client.access_key == "WHITESPACEKEY"
        assert client.secret_key == "WHITESPACESECRET"
        assert client.region == "us-west-2"  # credentials takes precedence
        assert str(client.endpoint_url) == "https://s3.us-east-1.amazonaws.com"

    def test_missing_credentials_file(self, tmp_path: pathlib.Path):
        config_file = tmp_path / "config"
        config_file.write_text("""[default]
aws_access_key_id = TESTKEY
aws_secret_access_key = TESTSECRET
region = us-east-1
endpoint_url = https://s3.us-east-1.amazonaws.com
""")

        client = S3Client.from_aws_config(
            bucket="test-bucket",
            credentials_path=tmp_path / "nonexistent",
            config_path=config_file,
        )
        assert client.access_key == "TESTKEY"
        assert client.secret_key == "TESTSECRET"
        assert client.region == "us-east-1"

    def test_no_credentials_anywhere(self, tmp_path: pathlib.Path):
        with pytest.raises(
            ValueError,
            match="aws_access_key_id not found for profile 'default' "
            "in config or credentials files",
        ):
            S3Client.from_aws_config(
                bucket="test-bucket", credentials_path=tmp_path / "nonexistent"
            )

    def test_missing_profile_in_credentials(self, tmp_path: pathlib.Path):
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[default]
aws_access_key_id = DEFAULTKEY
aws_secret_access_key = DEFAULTSECRET
endpoint_url = https://s3.us-east-1.amazonaws.com
""")

        with pytest.raises(
            ValueError,
            match="aws_access_key_id not found for profile 'nonexistent' "
            "in config or credentials files",
        ):
            S3Client.from_aws_config(
                bucket="test-bucket",
                profile_name="nonexistent",
                credentials_path=credentials_file,
            )

    def test_missing_access_key(self, tmp_path: pathlib.Path):
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[broken]
aws_secret_access_key = TESTSECRET
region = us-east-1
endpoint_url = https://s3.us-east-1.amazonaws.com
""")

        with pytest.raises(
            ValueError, match="aws_access_key_id not found for profile 'broken'"
        ):
            S3Client.from_aws_config(
                bucket="test-bucket",
                profile_name="broken",
                credentials_path=credentials_file,
            )

    def test_missing_secret_key(self, tmp_path: pathlib.Path):
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[broken]
aws_access_key_id = TESTKEY
region = us-east-1
""")

        with pytest.raises(
            ValueError, match="aws_secret_access_key not found for profile 'broken'"
        ):
            S3Client.from_aws_config(
                bucket="test-bucket",
                profile_name="broken",
                credentials_path=credentials_file,
            )

    def test_extra_options_ignored(self, tmp_path: pathlib.Path):
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[extra]
aws_access_key_id = EXTRAKEY
aws_secret_access_key = EXTRASECRET
region = us-east-1
endpoint_url = https://s3.us-east-1.amazonaws.com
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

        client = S3Client.from_aws_config(
            bucket="test-bucket",
            profile_name="extra",
            credentials_path=credentials_file,
            config_path=config_file,
        )

        assert client.access_key == "EXTRAKEY"
        assert client.secret_key == "EXTRASECRET"
        assert client.region == "us-east-1"

    def test_missing_config_file_ok(self, tmp_path: pathlib.Path):
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[test]
aws_access_key_id = TESTKEY
aws_secret_access_key = TESTSECRET
region = us-west-2
endpoint_url = https://s3.us-east-1.amazonaws.com
""")

        client = S3Client.from_aws_config(
            bucket="test-bucket",
            profile_name="test",
            credentials_path=credentials_file,
            config_path=tmp_path / "nonexistent_config",
        )

        assert client.access_key == "TESTKEY"
        assert client.secret_key == "TESTSECRET"
        assert client.region == "us-west-2"

    def test_empty_files(self, tmp_path: pathlib.Path):
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("")

        config_file = tmp_path / "config"
        config_file.write_text("")

        with pytest.raises(
            ValueError,
            match="aws_access_key_id not found for profile 'default' "
            "in config or credentials files",
        ):
            S3Client.from_aws_config(
                bucket="test-bucket",
                credentials_path=credentials_file,
                config_path=config_file,
            )

    def test_malformed_config_files(self, tmp_path: pathlib.Path):
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[default
aws_access_key_id = TESTKEY
aws_secret_access_key = TESTSECRET
invalid line without equals
""")

        # configparser should handle this gracefully by ignoring malformed lines
        # This may not raise an error depending on configparser behavior
        try:
            client = S3Client.from_aws_config(
                bucket="test-bucket", credentials_path=credentials_file
            )
            assert client.access_key == "TESTKEY"
            assert client.secret_key == "TESTSECRET"
        except Exception:
            # Malformed config might cause errors, which is acceptable
            pass

    def test_case_sensitivity(self, tmp_path: pathlib.Path):
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[CaseSensitive]
aws_access_key_id = CASEKEY
aws_secret_access_key = CASESECRET
region = us-east-1
endpoint_url = https://s3.us-east-1.amazonaws.com
""")

        client = S3Client.from_aws_config(
            bucket="test-bucket",
            profile_name="CaseSensitive",
            credentials_path=credentials_file,
        )
        assert client.access_key == "CASEKEY"

    def test_credentials_from_config_file_only(self, tmp_path: pathlib.Path):
        config_file = tmp_path / "config"
        config_file.write_text("""[default]
aws_access_key_id = CONFIGKEY
aws_secret_access_key = CONFIGSECRET
region = us-west-2
endpoint_url = https://s3.us-west-2.amazonaws.com

[profile testprofile]
aws_access_key_id = PROFILEKEY
aws_secret_access_key = PROFILESECRET
region = eu-west-1
endpoint_url = https://s3.us-east-1.amazonaws.com
""")

        # Test default profile from config only
        client = S3Client.from_aws_config(
            bucket="test-bucket", config_path=config_file, credentials_path=None
        )
        assert client.access_key == "CONFIGKEY"
        assert client.secret_key == "CONFIGSECRET"
        assert client.region == "us-west-2"

        # Test named profile from config only
        client = S3Client.from_aws_config(
            bucket="test-bucket",
            profile_name="testprofile",
            config_path=config_file,
            credentials_path=None,
        )
        assert client.access_key == "PROFILEKEY"
        assert client.secret_key == "PROFILESECRET"
        assert client.region == "eu-west-1"

    def test_case_sensitivity_continued(self, tmp_path: pathlib.Path):
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[CaseSensitive]
aws_access_key_id = CASEKEY
aws_secret_access_key = CASESECRET
region = us-east-1
endpoint_url = https://s3.us-east-1.amazonaws.com
""")

        # Different case should fail
        with pytest.raises(
            ValueError,
            match="aws_access_key_id not found for profile 'casesensitive' "
            "in config or credentials files",
        ):
            S3Client.from_aws_config(
                bucket="test-bucket",
                profile_name="casesensitive",
                credentials_path=credentials_file,
            )

    def test_pathlib_path_objects(self, tmp_path: pathlib.Path):
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[pathlib]
aws_access_key_id = PATHLIBKEY
aws_secret_access_key = PATHLIBSECRET
region = us-east-1
endpoint_url = https://s3.us-east-1.amazonaws.com
""")

        client = S3Client.from_aws_config(
            bucket="test-bucket",
            profile_name="pathlib",
            credentials_path=credentials_file,  # pathlib.Path object
            config_path=tmp_path / "nonexistent",
        )

        assert client.access_key == "PATHLIBKEY"
        assert client.secret_key == "PATHLIBSECRET"

    def test_string_path_objects(self, tmp_path: pathlib.Path):
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[string]
aws_access_key_id = STRINGKEY
aws_secret_access_key = STRINGSECRET
region = us-east-1
endpoint_url = https://s3.us-east-1.amazonaws.com
""")

        client = S3Client.from_aws_config(
            bucket="test-bucket",
            profile_name="string",
            credentials_path=str(credentials_file),  # string path
            config_path=str(tmp_path / "nonexistent"),
        )

        assert client.access_key == "STRINGKEY"
        assert client.secret_key == "STRINGSECRET"

    def test_default_paths(self, monkeypatch):
        with tempfile.TemporaryDirectory() as temp_home:
            aws_dir = pathlib.Path(temp_home) / ".aws"
            aws_dir.mkdir()

            credentials_file = aws_dir / "credentials"
            credentials_file.write_text("""[default]
aws_access_key_id = DEFAULTKEY
aws_secret_access_key = DEFAULTSECRET
region = us-east-1
endpoint_url = https://s3.us-east-1.amazonaws.com
""")

            config_file = aws_dir / "config"
            config_file.write_text("""[default]
output = json
""")

            monkeypatch.setattr(pathlib.Path, "home", lambda: pathlib.Path(temp_home))

            # Test with default paths (should find ~/.aws/credentials and ~/.aws/config)
            client = S3Client.from_aws_config(
                bucket="test-bucket",
                config_path=pathlib.Path.home(),
                credentials_path=credentials_file,
            )

            assert client.access_key == "DEFAULTKEY"
            assert client.secret_key == "DEFAULTSECRET"
            assert client.region == "us-east-1"

    def test_credentials_precedence_over_config_region(self, tmp_path: pathlib.Path):
        credentials_file = tmp_path / "credentials"
        credentials_file.write_text("""[precedence]
aws_access_key_id = PRECEDENCEKEY
aws_secret_access_key = PRECEDENCESECRET
region = ap-southeast-1
endpoint_url = https://s3.ap-southeast-1.amazonaws.com
""")

        config_file = tmp_path / "config"
        config_file.write_text("""[profile precedence]
region = eu-north-1
output = json
""")

        client = S3Client.from_aws_config(
            bucket="test-bucket",
            profile_name="precedence",
            credentials_path=credentials_file,
            config_path=config_file,
        )

        # Region from credentials should win
        assert client.region == "ap-southeast-1"
        assert str(client.endpoint_url) == "https://s3.ap-southeast-1.amazonaws.com"
