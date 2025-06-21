{
  description = "Papis-ask";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python3.override {
          packageOverrides = self: super: {
            paper-qa = import ./nix/pkgs/paper-qa { inherit pkgs python3Packages; };
            fhlmi = import ./nix/pkgs/fhlmi { inherit pkgs python3Packages; };
            fhaviary = import ./nix/pkgs/fhaviary { inherit pkgs python3Packages; };
            tantivy = import ./nix/pkgs/tantivy { inherit pkgs python3Packages; };
          };
        };
        python3Packages = python.pkgs;
      in
      {
        packages = {
          papis-ask = python3Packages.buildPythonPackage {
            pname = "papis-ask";
            version = if (self ? rev) then self.shortRev else self.dirtyShortRev;

            format = "pyproject";

            src = ./.;

            build-system = with python3Packages; [ hatchling ];

            buildInputs = with python3Packages; [
              papis
            ];

            dependencies = with python3Packages; [
              paper-qa
              click-default-group
              rich
            ];

            pythonImportsCheck = [ "papis_ask" ];

            # nativeCheckInputs = with python3Packages; [
            #   pytestCheckHook
            #   pytest-asyncio
            #   pytest-mock # TODO: needed?
            # ];

            meta = {
              description = "Use AI to search your Papis library";
              homepage = "https://papis.readthedocs.io/";
              license = with pkgs.lib.licenses; gpl3Plus;
              maintainers = [
                {
                  name = "Julian Hauser";
                  email = "julian@julianhauser.com";
                }
              ];
            };
          };
          default = self.packages.${system}.papis-ask;
        };

        devShells.default = pkgs.mkShell {
          buildInputs = [
            python
            pkgs.papis
            self.packages.${system}.papis-ask
          ];
          shellHook = ''
            export PYTHONPATH="$(pwd):$PYTHONPATH"
          '';
        };
      }
    );
}
