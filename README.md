# Papis-ask

This plugin for [Papis](https://github.com/papis/papis) integrates [paper-qa](https://github.com/whitead/paper-qa/) to allow you to use LLMs to ask questions about your library. Use it to search for documents or have it explain things to you. You can set it up to use a variety of local and online models. It is inspired by [isaksamsten](https://github.com/isaksamsten)'s excellent work on [papisqa](https://github.com/isaksamsten/papisqa).

Papis-ask is under active development. Expect bugs and changes.

## Installation

### Using pipx

Install papis (if not already installed):

```bash
$ pipx install papis
```

Then inject `papis-ask`:

```bash
$ pipx inject papis git+https://github.com/jghauser/papis-ask
```

### Using Nix Flake

Nix users can use the flake to create an overlay for Papis that includes Papis-ask.

<details>
  <summary>Nix configuration example</summary>

```nix
{
  description = "Papis-ask installation example";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

    papis-ask = {
      url = "github:jghauser/papis-ask"; # Replace with actual repository
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, papis-ask, ... }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        overlays = [
          (final: prev: {
            papis = prev.papis.overrideAttrs (oldAttrs: {
              propagatedBuildInputs = (oldAttrs.propagatedBuildInputs or []) ++ [
                papis-ask.packages.${system}.default
              ];
            });
          })
        ];
      };
    in {
      # NixOS system configuration
      nixosConfigurations.mySystem = nixpkgs.lib.nixosSystem {
        inherit system;
        modules = [
          ({ pkgs, ... }: {
            environment.systemPackages = [
              pkgs.papis
            ];
          })
        ];
      };
    };
}
```

</details>

## Configuration

Paper-qa (and hence Papis-ask) uses [liteLLM](https://github.com/BerriAI/litellm) for model access, which supports various LLM providers (Ollama, OpenAI, Anthropic, Google, etc.). You'll need to set up your models and API keys following the [liteLLM documentation](https://docs.litellm.ai/docs).

Configure the following settings in your Papis configuration file:

```
ask-llm = "your-preferred-llm-model"
ask-summary-llm = "your-preferred-summary-llm-model"
ask-embedding = "your-preferred-embedding-model"
```

I've had decent success using "ollama/nomic-embed-text" to create embeddings locally.

Additionally, you can set the settings that define defaults for the plugin's arguments. See the section on commands below for further information on what these settings do.

```
ask-evidence-k = 10
ask-max-sources = 5
ask-answer-length = "about 200 words, but can be longer"
ask-context = True
ask-excerpt = False
```

## Preparation

Papis-ask assumes various things about the state of your library: it assumes that your pdf files contain text and that metadata is complete and correct. There are various scripts in the `contrib` folder that can help you making sure the library is in a good state. Create backups and use at your own risk.

You might want to use the `ocrpdf.sh` script to OCR all PDFs that are missing embedded texts. The script is semi-smart at detecting which PDFs need to be processed and doesn't mess with annotations.

The `editor-author-list.py` and `fix-months.sh` scripts help fix the metadata in your `info.yaml` files. The first creates `author_list` and `editor_list` fields from `author` and `editor` fields, respectively. The second converts the `month` fields to an integer. Additionally, I suggest to use `papis doctor` to make sure the library doesn't contain any errors. Files will be indexed even if metadata is missing or false, but such mistakes might impact response quality.

## Commands

### Indexing your library

Before querying, you need to index your library:

```bash
$ papis ask index
```

Note that this can take a long time if you're indexing your whole library. Progress is saved after each document, and it's hence possible to interrupt the commmand and continue later.

You can also index specific documents (note that this will remove documents that *don't* match the query from the index):

```bash
$ papis ask index "author:einstein"
```

Use the `--force` or `-f` flag to regenerate the entire index:

```bash
$ papis ask index --force
```

### Querying your library

Ask questions about your library:

```bash
$ papis ask "What is the relationship between X and Y?"
```

Control the output format and level of detail:

```bash
$ papis ask "My question" --context/no-context    # Show context for each source (default: True)
$ papis ask "My question" --excerpt/no-excerpt    # Show context with excerpts (default: False)
$ papis ask "My question" --output markdown       # Output format, one of terminal/markdown/json (default: terminal)
$ papis ask "My question" --answer-length short   # Length of answer (default: "about 200 words, but can be longer")
$ papis ask "My question" --evidence-k 20         # Retrieve 20 pieces of evidence (default: 10)
$ papis ask "My question" --max-sources 10        # Use up to 10 sources in the answer (default: 5)
```

## Troubleshooting

### Papis library cache

Make sure your papis library's cache is up-to-date. Run `papis cache reset` when in doubt.

### Semantic Scholar

Papis-ask is querying Semantic Scholar for some metadata. This service is quite strictly rate-limited. Getting your own api key can help, though unfortunately there seems to be a long waitlist. Otherwise, rerunning the command is the only option at the moment.

## Screenshots

![2025-03-16T19:37:19,390782526+01:00](https://github.com/user-attachments/assets/6ff8e847-b0ca-45e0-a3f2-066d92b7f674)
