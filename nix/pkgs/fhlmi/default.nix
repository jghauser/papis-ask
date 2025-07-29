{
  pkgs,
  python3Packages,
}:
python3Packages.buildPythonPackage rec {
  pname = "fhlmi";
  format = "pyproject";
  version = "0.30.0";

  src = pkgs.fetchFromGitHub {
    owner = "Future-House";
    repo = "ldp";
    rev = "refs/tags/v${version}";
    hash = "sha256-/EGUBl1KDwxeuawjY5cZ0TEbpQyQM8/TQwDtxh1Bjc4=";
  };

  sourceRoot = "source/packages/lmi";

  propagatedBuildInputs = with python3Packages; [
    coredis
    fhaviary
    limits
    litellm
    pydantic
    tiktoken
    typing-extensions

    # optional
    tqdm
    types-tqdm
    # numpy
    # sentence-transformers
  ];

  pythonImportsCheck = [ "lmi" ];

  meta = {
    description = "A client to provide LLM responses for FutureHouse applications";
    homepage = "https://github.com/Future-House/ldp/packages/lmi";
    license = pkgs.lib.licenses.asl20;
  };
}
