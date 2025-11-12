"""Tools for generating a structured manifest of software projects in a repository."""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback for Python <3.11
    import tomli as tomllib  # type: ignore


IGNORED_DIRECTORIES = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "target",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "venv",
}


@dataclass
class ProjectDescriptor:
    """Describes the metadata captured for a single project inside the repo."""

    name: str
    path: str
    project_type: str
    language: str
    entrypoints: List[str] = field(default_factory=list)
    build_commands: List[str] = field(default_factory=list)
    test_commands: List[str] = field(default_factory=list)
    metadata: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "path": self.path,
            "project_type": self.project_type,
            "language": self.language,
            "entrypoints": sorted(set(self.entrypoints)),
            "build_commands": sorted(set(self.build_commands)),
            "test_commands": sorted(set(self.test_commands)),
            "metadata": self.metadata,
        }


class ManifestGenerator:
    """Generate a consolidated manifest describing projects inside a repository."""

    def __init__(self, root: Path | str, ignore: Optional[Iterable[str]] = None) -> None:
        self.root = Path(root).resolve()
        if not self.root.exists():
            raise FileNotFoundError(f"Repository root '{self.root}' does not exist")
        ignore_set = set(ignore or [])
        self.ignored_directories = IGNORED_DIRECTORIES.union(ignore_set)

    def generate(self) -> Dict[str, object]:
        """Return a manifest dictionary describing detected sub-projects."""

        projects: List[ProjectDescriptor] = []
        for directory, filenames in self._iter_project_files():
            path = Path(directory)
            if "package.json" in filenames:
                descriptor = self._parse_package_json(path / "package.json")
                if descriptor:
                    projects.append(descriptor)
            if "pyproject.toml" in filenames:
                descriptor = self._parse_pyproject(path / "pyproject.toml")
                if descriptor:
                    projects.append(descriptor)
            if "pom.xml" in filenames:
                descriptor = self._parse_pom(path / "pom.xml")
                if descriptor:
                    projects.append(descriptor)

        projects.sort(key=lambda project: project.path)

        manifest = {
            "project_root": str(self.root),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "projects": [project.to_dict() for project in projects],
        }
        return manifest

    # ------------------------------------------------------------------
    # project file iterators

    def _iter_project_files(self) -> Iterable[tuple[str, List[str]]]:
        for directory, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [
                d
                for d in dirnames
                if d not in self.ignored_directories and not d.startswith(".")
            ]
            yield directory, filenames

    # ------------------------------------------------------------------
    # Parsers

    def _parse_package_json(self, path: Path) -> Optional[ProjectDescriptor]:
        data = json.loads(path.read_text(encoding="utf-8"))
        name = data.get("name", path.parent.name)
        scripts = data.get("scripts", {})

        entrypoints: List[str] = []
        if main := data.get("main"):
            entrypoints.append(main)
        if module_entry := data.get("module"):
            entrypoints.append(module_entry)
        if exports := data.get("exports"):
            if isinstance(exports, str):
                entrypoints.append(exports)
            elif isinstance(exports, dict):
                entrypoints.extend(
                    value for value in exports.values() if isinstance(value, str)
                )
        if bins := data.get("bin"):
            if isinstance(bins, str):
                entrypoints.append(bins)
            elif isinstance(bins, dict):
                entrypoints.extend(bins.values())

        build_commands = self._scripts_with_keywords(scripts, ["build", "compile", "bundle"])
        test_commands = self._scripts_with_keywords(
            scripts, ["test", "lint", "coverage", "ci"]
        )

        metadata: Dict[str, object] = {
            "package_manager": data.get("packageManager"),
            "frameworks": self._detect_js_frameworks(data),
        }

        return ProjectDescriptor(
            name=name,
            path=str(path.parent.relative_to(self.root)),
            project_type="node",
            language="javascript",
            entrypoints=entrypoints,
            build_commands=build_commands,
            test_commands=test_commands,
            metadata=metadata,
        )

    def _parse_pyproject(self, path: Path) -> Optional[ProjectDescriptor]:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        project = data.get("project", {})
        name = project.get("name", path.parent.name)

        entrypoints: List[str] = []
        scripts = project.get("scripts", {})
        entrypoints.extend(
            value for value in scripts.values() if isinstance(value, str)
        )

        console_scripts = (
            project.get("entry-points", {})
            .get("console_scripts", {})
        )
        entrypoints.extend(
            value for value in console_scripts.values() if isinstance(value, str)
        )

        poetry_scripts = (
            data.get("tool", {}).get("poetry", {}).get("scripts", {})
        )
        entrypoints.extend(
            value for value in poetry_scripts.values() if isinstance(value, str)
        )

        unique_entrypoints = sorted(set(entrypoints))

        build_commands: List[str] = []
        if "tool" in data:
            tool = data["tool"]
            if "poetry" in tool:
                build_commands.append("poetry build")
                build_commands.append("poetry install")
            if "hatch" in tool:
                build_commands.append("hatch build")
        if (path.parent / "setup.cfg").exists() or (path.parent / "setup.py").exists():
            build_commands.append("python -m build")

        test_commands: List[str] = []
        if (path.parent / "pytest.ini").exists() or (path.parent / "tests").exists():
            test_commands.append("pytest")
        if (path.parent / "tox.ini").exists():
            test_commands.append("tox")
        if "tool" in data:
            tool = data["tool"]
            if "poetry" in tool:
                test_commands.append("poetry run pytest")
            if "hatch" in tool:
                test_commands.append("hatch run test")

        dependencies = project.get("dependencies", [])
        if isinstance(dependencies, dict):
            dependencies = [f"{name} {version}" for name, version in dependencies.items()]
        metadata = {
            "requires_python": project.get("requires-python"),
            "dependencies": dependencies,
        }

        return ProjectDescriptor(
            name=name,
            path=str(path.parent.relative_to(self.root)),
            project_type="python",
            language="python",
            entrypoints=unique_entrypoints,
            build_commands=sorted(set(build_commands)),
            test_commands=sorted(set(test_commands)),
            metadata=metadata,
        )

    def _parse_pom(self, path: Path) -> Optional[ProjectDescriptor]:
        tree = ET.parse(path)
        root = tree.getroot()
        ns = self._detect_namespace(root)

        def findtext(element: ET.Element, tag: str) -> Optional[str]:
            if ns:
                full_tag = f"{{{ns}}}{tag}"
            else:
                full_tag = tag
            found = element.find(full_tag)
            return found.text.strip() if found is not None and found.text else None

        artifact_id = findtext(root, "artifactId") or path.parent.name
        group_id = findtext(root, "groupId")
        version = findtext(root, "version")

        entrypoints: List[str] = []
        start_class = self._find_tag_with_fallback(root, ns, [
            "start-class",
            "mainClass",
        ])
        if start_class:
            entrypoints.append(start_class)

        metadata: Dict[str, object] = {
            "group_id": group_id,
            "version": version,
        }

        frameworks: List[str] = []
        for dependency in root.findall(f".//{{{ns}}}dependency" if ns else ".//dependency"):
            artifact = findtext(dependency, "artifactId")
            if artifact and artifact.startswith("spring-boot"):
                frameworks.append("spring-boot")
        metadata["frameworks"] = sorted(set(frameworks))

        build_commands = ["mvn package"]
        test_commands = ["mvn test"]

        return ProjectDescriptor(
            name=artifact_id,
            path=str(path.parent.relative_to(self.root)),
            project_type="maven",
            language="java",
            entrypoints=entrypoints,
            build_commands=build_commands,
            test_commands=test_commands,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # helpers

    @staticmethod
    def _scripts_with_keywords(scripts: Dict[str, str], keywords: List[str]) -> List[str]:
        matches: List[str] = []
        for name, command in scripts.items():
            for keyword in keywords:
                if keyword in name:
                    matches.append(f"npm run {name}")
                    break
                if keyword in command:
                    matches.append(command)
                    break
        return sorted(set(matches))

    @staticmethod
    def _detect_js_frameworks(data: Dict[str, object]) -> List[str]:
        frameworks: List[str] = []
        deps: Dict[str, str] = {}
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            value = data.get(key)
            if isinstance(value, dict):
                deps.update(value)
        mapping = {
            "react": "react",
            "next": "next.js",
            "vue": "vue",
            "@angular/core": "angular",
            "svelte": "svelte",
        }
        for package_name, framework_name in mapping.items():
            if package_name in deps:
                frameworks.append(framework_name)
        return sorted(set(frameworks))

    @staticmethod
    def _detect_namespace(element: ET.Element) -> Optional[str]:
        if element.tag.startswith("{"):
            return element.tag.split("}")[0][1:]
        return None

    @staticmethod
    def _find_tag_with_fallback(root: ET.Element, namespace: Optional[str], tags: List[str]) -> Optional[str]:
        for tag in tags:
            if namespace:
                full_tag = f"{{{namespace}}}{tag}"
            else:
                full_tag = tag
            found = root.find(f".//{full_tag}")
            if found is not None and found.text:
                return found.text.strip()
        return None
