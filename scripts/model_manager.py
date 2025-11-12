"""Model management utility for downloading and updating GGUF models.

This script is a cross-platform entry point that reads the manifest defined
in ``config/models.yaml`` and ensures all required models are available.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List

import yaml

MANIFEST_PATH = Path(__file__).resolve().parent.parent / "config" / "models.yaml"
DOWNLOAD_ROOT = Path(os.environ.get("LLM_MODELS_DIR", Path.home() / "llm_models"))
LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "model_manager.log"


def configure_logging(verbose: bool = False) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        filename=LOG_PATH,
        filemode="a",
        format="%(asctime)s [%(levelname)s] %(message)s",
        level=level,
    )
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logging.getLogger().addHandler(console)


def load_manifest() -> Dict[str, Dict[str, str]]:
    with MANIFEST_PATH.open("r", encoding="utf-8") as stream:
        manifest = yaml.safe_load(stream) or {}
    return manifest.get("models", {})

def ensure_downloader() -> List[str]:
    if shutil.which("aria2c"):
        return [
            "aria2c",
            "--max-connection-per-server=16",
            "--split=16",
            "--continue=true",
            "--dir",
            str(DOWNLOAD_ROOT),
        ]
    if shutil.which("curl"):
        return ["curl", "-L", "-o"]
    raise RuntimeError("No supported downloader found (aria2c or curl required)")


def calculate_checksum(path: Path, algorithm: str = "sha256") -> str:
    hash_func = hashlib.new(algorithm)
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hash_func.update(chunk)
    return hash_func.hexdigest()


def download_model(entry: Dict[str, str]) -> None:
    DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    target_path = DOWNLOAD_ROOT / entry["filename"]
    if target_path.exists() and entry.get("sha256"):
        current_hash = calculate_checksum(target_path)
        if current_hash == entry["sha256"]:
            logging.info("%s already present and verified", entry["filename"])
            return
        logging.warning("Checksum mismatch for %s, re-downloading", entry["filename"])
        target_path.unlink()

    downloader = ensure_downloader()
    if downloader[0] == "curl":
        command = downloader + [str(target_path), entry["url"]]
    else:
        command = downloader + [entry["url"]]
    logging.info("Downloading %s", entry["filename"])
    subprocess.run(command, check=True)

    if entry.get("sha256"):
        checksum = calculate_checksum(target_path)
        if checksum != entry["sha256"]:
            raise ValueError(f"Checksum mismatch for {entry['filename']}")
        logging.info("Verified checksum for %s", entry["filename"])


def prune_models(manifest: Dict[str, Dict[str, str]]) -> None:
    expected_files = {info["filename"] for info in manifest.values() if "filename" in info}
    for path in DOWNLOAD_ROOT.glob("*.gguf"):
        if path.name not in expected_files:
            logging.info("Pruning stale model %s", path.name)
            path.unlink()


def update_models(names: Iterable[str] | None = None) -> None:
    manifest = load_manifest()
    target_names = set(names) if names else set(manifest.keys())
    for name in target_names:
        entry = manifest.get(name)
        if not entry:
            logging.warning("Model %s not found in manifest", name)
            continue
        download_model(entry)
    prune_models(manifest)


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage GGUF models defined in config/models.yaml")
    parser.add_argument("models", nargs="*", help="Optional list of model identifiers to update")
    parser.add_argument("--prune-only", action="store_true", help="Only prune stale models")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    configure_logging(verbose=args.verbose)

    try:
        if args.prune_only:
            prune_models(load_manifest())
        else:
            update_models(args.models)
    except Exception as exc:  # pylint: disable=broad-except
        logging.exception("Model management failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

