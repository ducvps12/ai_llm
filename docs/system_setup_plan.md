# Multi-Machine LLM Workstation Setup Plan

## 1. Network Connectivity and Shared Repository Access
### Current Requirements
- Two workstations must access a shared source repository hosted on the local NAS.
- Remote collaboration should remain secure, with low administrative overhead.

### Recommended Topology
1. **Site-to-Site Virtual Network** using [ZeroTier](https://www.zerotier.com/):
   - Create a private ZeroTier network (e.g., `fd00:llm-net`).
   - Enroll both machines and the NAS. Assign static ZeroTier IPs (e.g., `10.17.0.10`, `10.17.0.11`, `10.17.0.20`).
   - Authorize members in the ZeroTier web console, tagging the NAS as a router if cross-subnet routing is required.
2. **Bandwidth Survey**:
   - Measure LAN throughput using `iperf3` between each workstation and the NAS.
   - Record baseline Wi-Fi vs. Ethernet results. Prefer wired 2.5GbE links for sustained model synchronization.
   - If upstream Internet bandwidth is limited (<100 Mbps), schedule large model syncs overnight.
3. **Repository Access**:
   - Host the Git bare repository on the NAS (`/srv/git/llm-repo.git`).
   - Mount NAS shares via SMB/NFS and expose only to ZeroTier addresses.
   - Configure SSH with `Match Address 10.17.0.*` rules to restrict access to the virtual network.

## 2. GPU Driver and CUDA/cuDNN Installation
### Machine A (GeForce RTX 4090, Ubuntu 22.04)
1. Remove existing NVIDIA packages:
   ```bash
   sudo apt purge 'nvidia-*' 'cuda-*' 'libnvidia-*'
   sudo apt autoremove
   ```
2. Install driver 550.xx from the official NVIDIA PPA:
   ```bash
   sudo add-apt-repository ppa:graphics-drivers/ppa
   sudo apt update
   sudo apt install nvidia-driver-550
   ```
3. Install CUDA Toolkit 12.4 and cuDNN 9.1 (runtime and developer packages):
   ```bash
   wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-ubuntu2204.pin
   sudo mv cuda-ubuntu2204.pin /etc/apt/preferences.d/cuda-repository-pin-600
   sudo apt-key adv --fetch-keys https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/3bf863cc.pub
   sudo add-apt-repository "deb https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/ /"
   sudo apt update
   sudo apt install cuda-toolkit-12-4 libcudnn9 libcudnn9-dev
   ```
4. Add environment variables to `/etc/profile.d/cuda.sh`:
   ```bash
   export PATH=/usr/local/cuda-12.4/bin:$PATH
   export LD_LIBRARY_PATH=/usr/local/cuda-12.4/lib64:$LD_LIBRARY_PATH
   ```

### Machine B (RTX 3080, Windows 11)
1. Download NVIDIA Game Ready Driver 552.xx or Studio Driver 552.xx (ensure CUDA 12.4 support).
2. Install CUDA Toolkit 12.3 (last toolkit officially validated for Ampere) and cuDNN 8.9.7 for Windows.
3. Verify using `nvidia-smi` and `nvcc --version` within PowerShell/WSL2.

### Validation
- Run CUDA samples (`deviceQuery`, `bandwidthTest`).
- Capture driver and CUDA versions in documentation for reproducibility.

## 3. LM Studio Installation and Benchmarking
### Deployment Steps
1. Download LM Studio latest releases for Windows and macOS/Linux as applicable.
2. Install on both machines, enabling GPU acceleration (ensure `llama.cpp` backend uses CUDA).
3. Configure model directory to point to shared NAS path (`Z:/LLM_Models` on Windows, `/mnt/llm_models` on Linux).

### Model Loading Tests
- Load a 7B GGUF model (e.g., `TheBloke/Llama-3-8B-Instruct-GGUF` in `Q4_K_M` quantization).
- Validate inference by running sample prompts.

### Benchmark Procedure
1. Within LM Studio, run the built-in benchmark or utilize CLI `lmstudio-cli benchmark --model path/to/model.gguf --context 4096`.
2. Record tokens-per-second (TPS) for 4K and 8K context lengths.
3. Compare results between machines and document GPU utilization via `nvidia-smi dmon` (Linux) or GPU-Z (Windows).

## 4. Model Management and Data Synchronization
### Script Outline (`scripts/model_manager.py`)
- Maintain a YAML manifest (`config/models.yaml`) listing model name, source URL, checksum, preferred quantization, and update cadence.
- Functions:
  - `sync_manifest()` – pull latest manifest from Git or remote URL.
  - `download_model(entry)` – download via `aria2c` with checksum verification.
  - `update_models()` – iterate manifest, compare local checksum, download updates.
  - `prune_models()` – remove models not in manifest or older than retention policy.
- Support cross-platform paths using `pathlib`.
- Log actions to `logs/model_manager.log`.

### Scheduling
- Linux: create systemd timer (`model-sync.service` + `model-sync.timer`) to run nightly at 02:00.
- Windows: use Task Scheduler to run `powershell.exe -File C:\scripts\model_manager.ps1` that wraps Python virtualenv.
- Ensure jobs run post-repository sync to avoid contention.

### Data Synchronization Workflow
1. Use `rclone` to mirror `/mnt/projects` to NAS every 6 hours.
2. Configure NAS snapshots (hourly for 24h, daily for 7 days) to protect against corruption.
3. Document recovery procedures and test quarterly.

## 5. Documentation and Monitoring
- Store configuration details in the shared repo under `infra/`.
- Maintain a runbook with troubleshooting steps for VPN, drivers, and LM Studio.
- Monitor GPU health (`nvidia-smi --query-gpu`) and network latency; alert via email/Slack when thresholds exceeded.

