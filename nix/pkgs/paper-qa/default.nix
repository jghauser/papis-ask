{
  pkgs,
  python3Packages,
}:
python3Packages.buildPythonPackage rec {
  pname = "paper-qa";
  version = "5.27.0";

  format = "pyproject";

  src = pkgs.fetchFromGitHub {
    owner = "Future-House";
    repo = "${pname}";
    rev = "refs/tags/v${version}";
    hash = "sha256-UawOu/TLWe66KClPSQLaxx+xdBosLoZ5h5K3aiAUgUc=";
  };

  propagatedBuildInputs = with python3Packages; [
    aiohttp
    anyio
    fhlmi
    fhaviary
    html2text
    httpx
    numpy
    pybtex
    pydantic-settings
    pydantic
    rich
    setuptools
    tantivy
    tenacity
    tiktoken
  ];

  # NOTE: to handle circular dependency between paper-qa and paper-qa-pypdf
  pythonRemoveDeps = [ "paper-qa-pypdf" ];
  passthru.optional-dependencies = {
    paper-qa-pypdf = [ python3Packages.paper-qa-pypdf ];
  };

  # NOTE: Disabled since it causes "> PermissionError: [Errno 13] Permission denied: '/homeless-shelter'"
  # pythonImportsCheck = ["paperqa"];

  meta = {
    homepage = "https://github.com/Future-House/paper-qa";
    description = "LLM Chain for answering questions from docs";
    license = pkgs.lib.licenses.asl20;
  };
}
