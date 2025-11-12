"""Utility package for analyzing repositories and preparing language-model artifacts."""

from .manifest import ManifestGenerator
from .embedding_pipeline import EmbeddingPipeline

__all__ = ["ManifestGenerator", "EmbeddingPipeline"]
