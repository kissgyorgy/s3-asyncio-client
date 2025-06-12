{ pkgs, config, ... }:

{
  env = {
    PYTHONPATH = "${config.env.DEVENV_ROOT}/src";
  };

  languages.python = {
    enable = true;
    venv.enable = true;
    uv = {
      enable = true;
      sync.enable = true;
    };
  };

  packages = with pkgs; [
    # Testing tools for S3 compatibility
    minio
    minio-client
  ];

  scripts = {
    test.exec = "python -m pytest tests/";
    lint.exec = "ruff check src/ tests/";
    format.exec = "ruff format src/ tests/";
    typecheck.exec = "mypy src/";
    serve-minio.exec = "minio server /tmp/minio-data --console-address :9001";
  };

  processes = {
    # Optional: automatically start minio in development
    # minio.exec = "minio server /tmp/minio-data --console-address :9001";
  };
}
