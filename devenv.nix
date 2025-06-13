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
    # Command runner
    just
  ];

  process.manager = {
    implementation = "mprocs";
  };

  processes = {
    minio.exec = "minio server ${config.devenv.root}/tmp/minio-data --console-address :9001";
    docs.exec = "mkdocs serve";
  };
}
