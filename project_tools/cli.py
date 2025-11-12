"""Command line entry point for repository analysis utilities."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List

from .embedding_pipeline import EmbeddingPipeline
from .manifest import ManifestGenerator


def _parse_ignore(values: Iterable[str] | None) -> List[str]:
    if not values:
        return []
    ignored: List[str] = []
    for value in values:
        ignored.extend([item.strip() for item in value.split(",") if item.strip()])
    return ignored


def build_manifest_command(args: argparse.Namespace) -> None:
    ignore = _parse_ignore(args.ignore)
    generator = ManifestGenerator(args.root, ignore=ignore)
    manifest = generator.generate()
    output_path = Path(args.output)
    output_path.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    if not args.quiet:
        print(f"Manifest written to {output_path}")


def build_embeddings_command(args: argparse.Namespace) -> None:
    ignore = _parse_ignore(args.ignore)
    pipeline = EmbeddingPipeline(
        model_name=args.model,
        ignore=ignore,
        include_hidden=args.include_hidden,
        max_file_size_kb=args.max_file_size,
        batch_size=args.batch_size,
    )
    pipeline.build_index(args.root, args.output)
    if not args.quiet:
        print(f"Embedding index written to {args.output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Utilities for extracting manifests and embeddings from a repository.",
    )
    parser.add_argument("--version", action="version", version="ai-llm-tools 0.1.0")

    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest_parser = subparsers.add_parser(
        "manifest", help="Generate a project_manifest.json for the repository"
    )
    manifest_parser.add_argument("root", nargs="?", default=".")
    manifest_parser.add_argument(
        "--output", default="project_manifest.json", help="Path to the output file"
    )
    manifest_parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        help="Comma-separated list of directories to ignore",
    )
    manifest_parser.add_argument("--quiet", action="store_true", help="Suppress logs")
    manifest_parser.set_defaults(func=build_manifest_command)

    embed_parser = subparsers.add_parser(
        "embed", help="Build an embedding index for the repository"
    )
    embed_parser.add_argument("root", nargs="?", default=".")
    embed_parser.add_argument(
        "--output",
        default="embedding_index.json",
        help="Where to store the embedding index",
    )
    embed_parser.add_argument(
        "--model",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Sentence-transformers model name to load",
    )
    embed_parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        help="Comma-separated list of directories to ignore",
    )
    embed_parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include files and directories starting with a dot",
    )
    embed_parser.add_argument(
        "--max-file-size",
        type=int,
        default=256,
        help="Maximum file size (in KB) to embed",
    )
    embed_parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="How many files to encode per batch",
    )
    embed_parser.add_argument("--quiet", action="store_true", help="Suppress logs")
    embed_parser.set_defaults(func=build_embeddings_command)

    return parser


def main(argv: List[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":  # pragma: no cover
    main()
