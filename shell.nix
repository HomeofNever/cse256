with (import (import ./nix/sources.nix).nixpkgs) { config.allowUnfree = true; };
stdenv.mkDerivation {
  name = "cse256";
  # nativeBuildInputs = [ cmake gcc  ];
  buildInputs = [ python3 niv pandoc texlive.combined.scheme-full ];
}