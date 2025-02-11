{ pkgs }: {
  deps = [
    pkgs.rustc
    pkgs.libiconv
    pkgs.cargo
    pkgs.libxcrypt
    pkgs.bash
    (pkgs.python310.withPackages(ps: [
      ps.pip
      ps.daphne
      ps.pydantic
      ps.typing-extensions
      ps.boto3
    ]))
    pkgs.postgresql
    pkgs.sqlite-interactive
    pkgs.openssl_3_1
    pkgs.libffi
    pkgs.pkg-config
  ];
  env = rec {
    PYTHONPATH = "${pkgs.python310}/lib/python3.10/site-packages:$HOME/.local/lib/python3.10/site-packages:$HOME/.pythonlibs/lib/python3.10/site-packages";
    LD_LIBRARY_PATH = "${pkgs.openssl_3_1}/lib:${pkgs.libffi}/lib";
    PKG_CONFIG_PATH = "${pkgs.openssl_3_1.dev}/lib/pkgconfig";
    SSL_CERT_FILE = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
    OPENSSL_CONF = "${pkgs.openssl_3_1}/etc/ssl/openssl.cnf";
    PIP_USER = "1";
  };
}