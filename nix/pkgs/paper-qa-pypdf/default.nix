{
  pkgs,
  python3Packages,
}:
python3Packages.buildPythonPackage rec {
  pname = "paper-qa-pypdf";
  format = "pyproject";
  version = "5.27.0";

  src = pkgs.fetchFromGitHub {
    owner = "Future-House";
    repo = "paper-qa";
    rev = "refs/tags/v${version}";
    hash = "sha256-UawOu/TLWe66KClPSQLaxx+xdBosLoZ5h5K3aiAUgUc=";
  };

  sourceRoot = "source/packages/paper-qa-pypdf";

  propagatedBuildInputs = with python3Packages; [
    pypdf
    paper-qa
  ];

  build-system = with python3Packages; [
    setuptools
    setuptools-scm
  ];

  pythonImportsCheck = [ "paperqa_pypdf" ];

  meta = {
    description = "PaperQA readers implemented using PyPDF";
    homepage = "https://github.com/Future-House/paper-qa";
    license = pkgs.lib.licenses.asl20;
  };
}
