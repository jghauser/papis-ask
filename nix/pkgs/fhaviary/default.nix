{
  pkgs,
  python3Packages,
}:
python3Packages.buildPythonPackage rec {
  pname = "fhaviary";
  version = "0.22.1";

  format = "pyproject";

  src = pkgs.fetchFromGitHub {
    owner = "Future-House";
    repo = "aviary";
    rev = "refs/tags/v${version}";
    hash = "sha256-ZMJkcp5P1VS/ryKgxCEYFT1wdoBxhX0oeDnruOvPvCk=";
  };

  propagatedBuildInputs = with python3Packages; [
    docstring-parser
    httpx
    pydantic
    setuptools
    setuptools-scm
  ];

  pythonImportsCheck = [ "aviary" ];

  meta = {
    description = "Gymnasium framework for training language model agents on constructive tasks";
    homepage = "https://github.com/Future-House/aviary";
    license = pkgs.lib.licenses.asl20;
  };
}
