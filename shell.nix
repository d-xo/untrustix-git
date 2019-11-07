let
  pkgs = import (
    fetchGit {
      url = https://github.com/NixOS/nixpkgs-channels;
      ref = "nixos-19.09";
    }
  ) {};
in
pkgs.mkShell {
  name = "untrustix-git";
  buildInputs = with pkgs; [
    git
    mypy
    nix
    python3Packages.black
    (python3.withPackages (ps: with ps; [ pygit2 ]))
  ];
  NIX_PATH = "nixpkgs=${pkgs.path}";
}

