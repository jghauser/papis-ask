{
  pkgs,
  python3Packages,
}:
python3Packages.buildPythonPackage rec {
  pname = "tantivy";
  version = "2025-01-01-unstable"; # NOTE: latest stable doesn't build (easily) because of API changes in Rust 1.80 so we're using a more modern version

  format = "pyproject";

  src = pkgs.fetchFromGitHub {
    owner = "quickwit-oss";
    repo = "tantivy-py";
    # rev = version;
    rev = "master";
    hash = "sha256-bKgwwRPB0QnhvcXKq4NwnEPcD9LEEWHjFMpMi3mg0rU=";
  };

  cargoDeps = pkgs.rustPlatform.fetchCargoVendor {
    inherit src;
    name = "${pname}-${version}";
    hash = "sha256-rOimDblAsc1sYHNDhTPw3BVyX/NeoBYN85C0Q6IZfK8=";
  };

  nativeBuildInputs = with pkgs.rustPlatform; [
    cargoSetupHook
    maturinBuildHook
  ];

  pythonImportsCheck = [ "tantivy" ];

  meta = {
    description = " Python bindings for Tantivy ";
    homepage = "https://github.com/quickwit-oss/tantivy-py";
    license = pkgs.lib.licenses.mit;
  };
}
