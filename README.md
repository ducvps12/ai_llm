# ai_llm

This repository documents the infrastructure plan for a dual-workstation LLM
environment and provides tooling to automate GGUF model management.

- Refer to [`docs/system_setup_plan.md`](docs/system_setup_plan.md) for the full
  network, GPU, and software deployment plan.
- Use [`scripts/model_manager.py`](scripts/model_manager.py) with the manifest
  defined in [`config/models.yaml`](config/models.yaml) to download and maintain
  shared models on the NAS.
