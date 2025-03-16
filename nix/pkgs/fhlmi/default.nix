{
  pkgs,
  python3Packages,
}:
python3Packages.buildPythonPackage rec {
  pname = "fhlmi";
  format = "pyproject";
  version = "0.25.4";

  src = pkgs.fetchFromGitHub {
    owner = "Future-House";
    repo = "ldp";
    rev = "refs/tags/v${version}";
    hash = "sha256-BJoBGg/UVd9JwABdWU7l2iXSBIFi2CwFBldDdI/vzyQ=";
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

  pythonImportsCheck = ["lmi"];

  meta = {
    description = "A client to provide LLM responses for FutureHouse applications";
    homepage = "https://github.com/Future-House/ldp/packages/lmi";
    license = pkgs.lib.licenses.asl20;
  };
}
