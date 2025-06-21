{
  pkgs,
  python3Packages,
}:
python3Packages.buildPythonPackage rec {
  pname = "paper-qa";
  version = "5.21.0";

  format = "pyproject";

  src = pkgs.fetchFromGitHub {
    owner = "Future-House";
    repo = "${pname}";
    rev = "refs/tags/v${version}";
    hash = "sha256-jrLMKGHIudo7yQH64vlrExnLytXAZhG+6GWBwb9NIBA=";
  };

  propagatedBuildInputs = with python3Packages; [
    pymupdf
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

  # NOTE: Disabled since it causes "> PermissionError: [Errno 13] Permission denied: '/homeless-shelter'"
  # pythonImportsCheck = ["paperqa"];

  meta = {
    homepage = "https://github.com/Future-House/paper-qa";
    description = "LLM Chain for answering questions from docs";
    license = pkgs.lib.licenses.asl20;
  };
}
