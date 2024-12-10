{ pkgs }: {
  deps = [
    pkgs.bash
    pkgs.python310
    pkgs.python310Packages.pip
    pkgs.python310Packages.daphne
    pkgs.postgresql
    pkgs.sqlite-interactive
    pkgs.openssl
    pkgs.libffi
    pkgs.pkg-config
  ];
  env = {
    PYTHONPATH = "$HOME/.local/lib/python3.10/site-packages:$HOME/.pythonlibs/lib/python3.10/site-packages:${pkgs.python310}/lib/python3.10/site-packages:$PYTHONPATH";
    LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
      pkgs.libffi
      pkgs.openssl
    ];
    PKG_CONFIG_PATH = "${pkgs.openssl.dev}/lib/pkgconfig";
    PIP_USER = "1";
  };
}