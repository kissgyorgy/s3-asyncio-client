"""Pytest configuration and fixtures."""

import configparser
import pathlib


def pytest_addoption(parser):
    """Add custom command line options for pytest."""
    parser.addoption(
        "--aws-config",
        action="store",
        default=None,
        help="Path to AWS config file to use for S3Client configuration",
    )


def get_aws_profiles(config_path: str | None) -> list[str]:
    """Extract all profiles from AWS config file.

    Args:
        config_path: Path to AWS config file or None for default minio profile

    Returns:
        List of profile names
    """
    if not config_path:
        return ["minio-default"]

    config_file = pathlib.Path(config_path)
    if not config_file.exists():
        return ["minio-default"]

    parser = configparser.ConfigParser()
    parser.read(config_file)

    profiles = []
    for section_name in parser.sections():
        if section_name == "default":
            profiles.append("default")
        elif section_name.startswith("profile "):
            # Config file uses "profile <name>" format
            profile_name = section_name[8:]  # Remove "profile " prefix
            profiles.append(profile_name)
        else:
            # Credentials file uses direct profile names
            profiles.append(section_name)

    return profiles if profiles else ["minio-default"]


def pytest_generate_tests(metafunc):
    """Generate test parameters dynamically based on AWS config profiles."""

    if "client" not in metafunc.fixturenames:
        return
    aws_config_path = metafunc.config.getoption("--aws-config")
    aws_profiles = get_aws_profiles(aws_config_path)
    metafunc.parametrize("client", aws_profiles, indirect=True)
