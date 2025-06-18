import configparser
import pathlib


def pytest_addoption(parser):
    parser.addoption(
        "--aws-config",
        action="store",
        default=None,
        help="Path to AWS config file to use for S3Client configuration",
    )


def get_aws_profiles(config_path: str | None) -> list[str]:
    """Parse all profiles from AWS config file. To use in tests for real S3 access."""
    if not config_path:
        config_path = "tmp/ovh_config"

    config_file = pathlib.Path(config_path)
    if not config_file.exists():
        return ["ovh"]

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

    return profiles if profiles else ["ovh"]


def pytest_generate_tests(metafunc):
    if "client" not in metafunc.fixturenames:
        return
    aws_config_path = metafunc.config.getoption("--aws-config")
    aws_profiles = get_aws_profiles(aws_config_path)
    metafunc.parametrize("client", aws_profiles, indirect=True)
