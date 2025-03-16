# Papis-ask

This plugin for [Papis](https://github.com/papis/papis) allows you to query and interact with your document library using large language models (LLMs). Papis-ask integrates [paper-qa](https://github.com/whitead/paper-qa/) with Papis to provide intelligent document search and question answering capabilities using natural language. It is inspired by the excellent work done by [isaksamsten](https://github.com/isaksamsten) on [papisqa](https://github.com/isaksamsten/papisqa).

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

For Nix users, there's a Flake.

## Configuration

Paper-qa (and hence Papis-ask) uses [liteLLM](https://github.com/BerriAI/litellm) for model access, which supports various LLM providers (Ollama, OpenAI, Anthropic, Google, etc.). You'll need to set up your models and API keys following the [liteLLM documentation](https://docs.litellm.ai/docs).

Configure the following settings in your Papis configuration file:

```
ask-llm = "your-preferred-llm-model"
ask-summary-llm = "your-preferred-summary-llm-model"
ask-embedding = "your-preferred-embedding-model"
```

I've had decent success using "ollama/nomic-embed-text" to create the embeddings locally.

## Preparation

You might want to use the `contrib/ocrpdf.sh` script to OCR all PDFs that are missing embedded texts. The script is semi-smart at detecting which PDFs need to be processed and doesn't mess with annotations. Create backups and use at your own risk.

## Commands

### Indexing your library

Before querying, you need to index your library:

```bash
$ papis ask index
```

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
$ papis ask "My question" --context         # Show context for each source (default: False)
$ papis ask "My question" --excerpt         # Show context with excerpts (default: False)
$ papis ask "My question" --to-json         # Output in JSON format (default: False)
$ papis ask "My question" --evidence-k 20   # Retrieve 20 pieces of evidence (default: 10)
$ papis ask "My question" --max-sources 1   # Use up to 8 sources in the answer (default: 5)
```

## Screenshots

