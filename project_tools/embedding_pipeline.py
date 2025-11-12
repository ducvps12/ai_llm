"""Embedding pipeline that indexes repository files for retrieval tasks."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence


@dataclass
class EmbeddingRecord:
    path: str
    type: str  # "file" or "directory"
    embedding: List[float]
    metadata: Dict[str, object]

    def to_dict(self) -> Dict[str, object]:
        return {
            "path": self.path,
            "type": self.type,
            "embedding": self.embedding,
            "metadata": self.metadata,
        }


class EmbeddingPipeline:
    """Generate embeddings for every file and directory in a repository tree."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        ignore: Optional[Iterable[str]] = None,
        include_hidden: bool = False,
        max_file_size_kb: int = 256,
        batch_size: int = 8,
    ) -> None:
        self.model_name = model_name
        self.ignore = set(ignore or [])
        self.include_hidden = include_hidden
        self.max_file_size = max_file_size_kb * 1024
        self.batch_size = batch_size
        self._model = None

    # ------------------------------------------------------------------
    # public API

    def build_index(self, root: str | Path, output_path: str | Path) -> Dict[str, object]:
        root_path = Path(root).resolve()
        if not root_path.exists():
            raise FileNotFoundError(root)

        records: List[EmbeddingRecord] = []
        file_vectors: Dict[Path, List[float]] = {}

        texts: List[str] = []
        files: List[Path] = []
        for file_path in self._iter_files(root_path):
            content = self._read_text(file_path)
            if not content:
                continue
            texts.append(content)
            files.append(file_path)
            if len(texts) >= self.batch_size:
                vectors = self._encode_batch(texts)
                for file, vector in zip(files, vectors):
                    file_vectors[file] = vector
                    records.append(
                        EmbeddingRecord(
                            path=self._relative_path(root_path, file),
                            type="file",
                            embedding=vector,
                            metadata={"size_bytes": file.stat().st_size},
                        )
                    )
                texts.clear()
                files.clear()

        if texts:
            vectors = self._encode_batch(texts)
            for file, vector in zip(files, vectors):
                file_vectors[file] = vector
                records.append(
                    EmbeddingRecord(
                        path=self._relative_path(root_path, file),
                        type="file",
                        embedding=vector,
                        metadata={"size_bytes": file.stat().st_size},
                    )
                )

        directory_vectors: Dict[Path, List[List[float]]] = {}
        for file_path, vector in file_vectors.items():
            parent = file_path.parent
            while True:
                directory_vectors.setdefault(parent, []).append(vector)
                if parent == root_path:
                    break
                parent = parent.parent

        for directory, vectors in directory_vectors.items():
            records.append(
                EmbeddingRecord(
                    path=self._relative_path(root_path, directory),
                    type="directory",
                    embedding=self._mean(vectors),
                    metadata={"children": len(vectors)},
                )
            )

        index = {
            "model": self.model_name,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "root": str(root_path),
            "records": [record.to_dict() for record in records],
        }

        output_path = Path(output_path)
        output_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
        return index

    # ------------------------------------------------------------------
    # helpers

    def _iter_files(self, root: Path) -> Iterator[Path]:
        for directory, dirnames, filenames in os.walk(root):
            dir_path = Path(directory)
            dirnames[:] = [
                d
                for d in dirnames
                if (self.include_hidden or not d.startswith("."))
                and d not in self.ignore
                and d not in {".git", "node_modules", "build", "dist", "target"}
            ]
            for filename in filenames:
                if not self.include_hidden and filename.startswith("."):
                    continue
                file_path = dir_path / filename
                if file_path.suffix in {".png", ".jpg", ".jpeg", ".gif", ".zip", ".jar"}:
                    continue
                if file_path.stat().st_size > self.max_file_size:
                    continue
                yield file_path

    def _read_text(self, path: Path) -> Optional[str]:
        try:
            data = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                data = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                return None
        if "\x00" in data:
            return None
        return data.strip()

    def _encode_batch(self, texts: Sequence[str]) -> List[List[float]]:
        model = self._load_model()
        embeddings = model.encode(
            list(texts), batch_size=min(self.batch_size, len(texts))
        )
        return [self._to_list(vector) for vector in embeddings]

    def _load_model(self):  # pragma: no cover - requires heavy dependency
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - environment-specific
            raise RuntimeError(
                "sentence-transformers is required for embedding generation."
            ) from exc
        self._model = SentenceTransformer(self.model_name)
        return self._model

    @staticmethod
    def _to_list(vector) -> List[float]:
        try:
            return [float(value) for value in vector.tolist()]
        except AttributeError:
            return [float(value) for value in vector]

    @staticmethod
    def _mean(vectors: Sequence[Sequence[float]]) -> List[float]:
        if not vectors:
            return []
        length = len(vectors[0])
        totals = [0.0] * length
        for vector in vectors:
            for index, value in enumerate(vector):
                totals[index] += float(value)
        count = float(len(vectors))
        return [total / count for total in totals]

    @staticmethod
    def _relative_path(root: Path, path: Path) -> str:
        try:
            rel = path.relative_to(root)
            return rel.as_posix() or "."
        except ValueError:
            return path.as_posix()
