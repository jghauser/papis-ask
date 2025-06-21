{
  pkgs,
  python3Packages,
}:
python3Packages.buildPythonPackage rec {
  pname = "tantivy";
  version = "0.24.0";

  format = "pyproject";

  src = pkgs.fetchFromGitHub {
    owner = "quickwit-oss";
    repo = "tantivy-py";
    rev = version;
    hash = "sha256-ZwmhOkNvKZaFPk7swxm+T3VxI7LlWDq//JjiLT23o8s=";
  };

  cargoDeps = pkgs.rustPlatform.fetchCargoVendor {
    inherit src;
    name = "${pname}-${version}";
    hash = "sha256-7QHUKOUhPQy+tc1JEB/+MGsPy8LKej5TSScw5LYXZlw=";
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
