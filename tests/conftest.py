"""
Pytest configuration and fixtures for SBOM Generator tests.
"""

import pytest
from pathlib import Path


# Path to test fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def sample_yarn_lock(fixtures_dir: Path) -> Path:
    """Return the path to sample yarn.lock file."""
    return fixtures_dir / "yarn.lock"


@pytest.fixture
def sample_package_json(fixtures_dir: Path) -> Path:
    """Return the path to sample package.json file."""
    return fixtures_dir / "package.json"


@pytest.fixture
def sample_gemfile_lock(fixtures_dir: Path) -> Path:
    """Return the path to sample Gemfile.lock file."""
    return fixtures_dir / "Gemfile.lock"


@pytest.fixture
def sample_requirements_txt(fixtures_dir: Path) -> Path:
    """Return the path to sample requirements.txt file."""
    return fixtures_dir / "requirements.txt"


@pytest.fixture
def sample_dockerfile(fixtures_dir: Path) -> Path:
    """Return the path to sample Dockerfile."""
    return fixtures_dir / "Dockerfile"
