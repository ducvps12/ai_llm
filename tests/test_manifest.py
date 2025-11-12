from __future__ import annotations

import shutil
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from project_tools.manifest import ManifestGenerator


@pytest.fixture()
def sample_repo(tmp_path: Path) -> Path:
    examples_dir = Path(__file__).resolve().parent.parent / "examples"
    shutil.copytree(examples_dir / "react_app", tmp_path / "react_app")
    shutil.copytree(examples_dir / "spring_boot_app", tmp_path / "spring_boot_app")
    return tmp_path


def test_manifest_detects_sample_projects(sample_repo: Path) -> None:
    generator = ManifestGenerator(sample_repo)
    manifest = generator.generate()

    assert manifest["project_root"] == str(sample_repo)
    assert manifest["projects"], "Expected at least one detected project"

    react_project = next(
        project
        for project in manifest["projects"]
        if project["name"] == "example-react-app"
    )
    assert react_project["project_type"] == "node"
    assert react_project["path"] == "react_app"
    assert "src/index.jsx" in react_project["entrypoints"]
    assert "npm run build" in react_project["build_commands"]
    assert any("test" in cmd for cmd in react_project["test_commands"])
    assert "react" in react_project["metadata"]["frameworks"]

    spring_project = next(
        project
        for project in manifest["projects"]
        if project["name"] == "spring-boot-sample"
    )
    assert spring_project["project_type"] == "maven"
    assert spring_project["path"] == "spring_boot_app"
    assert spring_project["entrypoints"] == ["com.example.Application"]
    assert spring_project["build_commands"] == ["mvn package"]
    assert spring_project["test_commands"] == ["mvn test"]
    assert "spring-boot" in spring_project["metadata"]["frameworks"]
