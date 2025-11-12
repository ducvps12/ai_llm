# ai_llm Toolkit

Utilities for analysing source repositories and preparing context for LLM-based
assistants. The toolkit ships with a CLI that can produce a project manifest and
an embedding index, an embedding pipeline built on top of
[`sentence-transformers`](https://www.sbert.net/), and prompt templates that can
be imported into LM Studio.

## Installation

Create a virtual environment and install the package in editable mode:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

> **Note**: Generating embeddings requires the `sentence-transformers`
dependency and will attempt to download the configured model on first use.

## CLI usage

The CLI exposes two sub-commands. Run `python -m project_tools.cli --help` for
an overview.

### Generate a manifest

```bash
python -m project_tools.cli manifest /path/to/repo --output project_manifest.json
```

The manifest includes detected entrypoints, build commands, test commands, and
key metadata for Node.js, Python, and Maven-based (Spring Boot) projects. Use
`--ignore` to skip directories (value accepts comma-separated lists and can be
repeated).

### Build an embedding index

```bash
python -m project_tools.cli embed /path/to/repo \
  --model sentence-transformers/all-MiniLM-L6-v2 \
  --output embedding_index.json
```

Embedding generation walks the repository, skipping common build artefacts and
large/binary files. Directory vectors are produced by averaging the vectors of
contained files, enabling hierarchical retrieval.

## Prompt templates for LM Studio

The file [`project_tools/prompts/architecture_summary.yaml`](project_tools/prompts/architecture_summary.yaml)
contains a template focused on architecture summarisation and dependency graph
exploration. Import it into LM Studio and fill in the variables with data from
the manifest and your own observations.

## Examples and testing

Sample React and Spring Boot projects are available in [`examples/`](examples/)
for manual experimentation. Automated coverage for manifest extraction lives in
[`tests/test_manifest.py`](tests/test_manifest.py). Run the test suite with:

```bash
pytest
```
