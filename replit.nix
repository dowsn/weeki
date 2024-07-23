{ pkgs }: {
  deps = [
    pkgs.postgresql
    pkgs.postgresql_16_jit
    pkgs.sqlite-interactive
    pkgs.python310
    pkgs.python310Packages.pip
    pkgs.python310Packages.virtualenv
    pkgs.ffmpeg 
    pkgs.nvidia-podman
    pkgs.linuxHeaders
    pkgs.portaudio
    pkgs.gettext
    pkgs.zlib
    pkgs.tk
    pkgs.tcl
    pkgs.openjpeg
    pkgs.libxcrypt
    pkgs.libwebp
    pkgs.libtiff
    pkgs.libjpeg
    pkgs.libimagequant
    pkgs.lcms2
    pkgs.freetype
  ];

  shellHook = ''
    if [ ! -d .venv ]; then
      virtualenv .venv
    fi
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
  '';
}