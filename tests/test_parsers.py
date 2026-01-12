"""
Tests for SBOM parsers.
"""

import pytest
from pathlib import Path
import shutil
import tempfile

from sbom.parsers import (
    YarnParser,
    GemfileParser,
    RequirementsParser,
    DockerfileParser,
)
from sbom.models import PackageType


class TestYarnParser:
    """Tests for YarnParser."""

    def test_can_parse_yarn_lock(self, sample_yarn_lock: Path):
        """Test that YarnParser can identify yarn.lock files."""
        parser = YarnParser()
        assert parser.can_parse(sample_yarn_lock)

    def test_cannot_parse_other_files(self, sample_gemfile_lock: Path):
        """Test that YarnParser rejects non-yarn.lock files."""
        parser = YarnParser()
        assert not parser.can_parse(sample_gemfile_lock)

    def test_parse_yarn_lock(self, sample_yarn_lock: Path, sample_package_json: Path):
        """Test parsing yarn.lock file."""
        # Copy package.json to same directory as yarn.lock for direct dependency detection
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            yarn_lock = tmpdir_path / "yarn.lock"
            package_json = tmpdir_path / "package.json"
            
            shutil.copy(sample_yarn_lock, yarn_lock)
            shutil.copy(sample_package_json, package_json)
            
            parser = YarnParser()
            packages = parser.parse(yarn_lock)
            
            # Verify packages were parsed
            assert len(packages) > 0
            
            # Verify package type
            for pkg in packages:
                assert pkg.package_type == PackageType.NPM
            
            # Verify known packages exist
            package_names = {pkg.name for pkg in packages}
            assert "express" in package_names
            assert "lodash" in package_names
            
            # Verify direct dependencies are marked
            express_pkg = next(p for p in packages if p.name == "express")
            assert express_pkg.is_direct_dependency

    def test_parse_yarn_lock_extracts_dependencies(self, sample_yarn_lock: Path):
        """Test that dependencies are extracted from yarn.lock."""
        parser = YarnParser()
        packages = parser.parse(sample_yarn_lock)
        
        # Find express package
        express_pkg = next((p for p in packages if p.name == "express"), None)
        assert express_pkg is not None
        
        # Verify express has dependencies
        assert len(express_pkg.dependencies) > 0
        assert "accepts" in express_pkg.dependencies


class TestGemfileParser:
    """Tests for GemfileParser."""

    def test_can_parse_gemfile_lock(self, sample_gemfile_lock: Path):
        """Test that GemfileParser can identify Gemfile.lock files."""
        parser = GemfileParser()
        assert parser.can_parse(sample_gemfile_lock)

    def test_cannot_parse_other_files(self, sample_yarn_lock: Path):
        """Test that GemfileParser rejects non-Gemfile.lock files."""
        parser = GemfileParser()
        assert not parser.can_parse(sample_yarn_lock)

    def test_parse_gemfile_lock(self, sample_gemfile_lock: Path):
        """Test parsing Gemfile.lock file."""
        parser = GemfileParser()
        packages = parser.parse(sample_gemfile_lock)
        
        # Verify packages were parsed
        assert len(packages) > 0
        
        # Verify package type
        for pkg in packages:
            assert pkg.package_type == PackageType.RUBYGEMS
        
        # Verify known packages exist
        package_names = {pkg.name for pkg in packages}
        assert "rails" in package_names
        assert "activesupport" in package_names

    def test_parse_gemfile_lock_direct_dependencies(self, sample_gemfile_lock: Path):
        """Test that direct dependencies are marked correctly."""
        parser = GemfileParser()
        packages = parser.parse(sample_gemfile_lock)
        
        # rails should be a direct dependency
        rails_pkg = next((p for p in packages if p.name == "rails"), None)
        assert rails_pkg is not None
        assert rails_pkg.is_direct_dependency
        
        # concurrent-ruby should NOT be a direct dependency
        concurrent_pkg = next((p for p in packages if p.name == "concurrent-ruby"), None)
        assert concurrent_pkg is not None
        assert not concurrent_pkg.is_direct_dependency


class TestRequirementsParser:
    """Tests for RequirementsParser."""

    def test_can_parse_requirements_txt(self, sample_requirements_txt: Path):
        """Test that RequirementsParser can identify requirements.txt files."""
        parser = RequirementsParser()
        assert parser.can_parse(sample_requirements_txt)

    def test_cannot_parse_other_files(self, sample_yarn_lock: Path):
        """Test that RequirementsParser rejects non-requirements.txt files."""
        parser = RequirementsParser()
        assert not parser.can_parse(sample_yarn_lock)

    def test_parse_requirements_txt(self, sample_requirements_txt: Path):
        """Test parsing requirements.txt file."""
        parser = RequirementsParser()
        packages = parser.parse(sample_requirements_txt)
        
        # Verify packages were parsed
        assert len(packages) == 3  # requests, flask, pytest
        
        # Verify package type
        for pkg in packages:
            assert pkg.package_type == PackageType.PYPI
        
        # Verify known packages exist
        package_names = {pkg.name for pkg in packages}
        assert "requests" in package_names
        assert "flask" in package_names
        assert "pytest" in package_names

    def test_parse_requirements_txt_all_direct_dependencies(self, sample_requirements_txt: Path):
        """Test that all packages in requirements.txt are marked as direct dependencies."""
        parser = RequirementsParser()
        packages = parser.parse(sample_requirements_txt)
        
        # All packages should be direct dependencies
        for pkg in packages:
            assert pkg.is_direct_dependency

    def test_parse_requirements_txt_version_extraction(self, sample_requirements_txt: Path):
        """Test that versions are extracted correctly."""
        parser = RequirementsParser()
        packages = parser.parse(sample_requirements_txt)
        
        # Find flask package (has exact version)
        flask_pkg = next((p for p in packages if p.name == "flask"), None)
        assert flask_pkg is not None
        assert flask_pkg.version == "2.3.0"
        
        # Find pytest package (no version)
        pytest_pkg = next((p for p in packages if p.name == "pytest"), None)
        assert pytest_pkg is not None
        assert pytest_pkg.version == ""

    def test_skip_comments_and_empty_lines(self):
        """Test that comments and empty lines are skipped."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("# This is a comment\n")
            f.write("\n")
            f.write("requests>=2.28.0\n")
            f.write("  # Another comment\n")
            f.write("flask==2.3.0\n")
            f.name
            
        try:
            # Rename to requirements.txt for parser to recognize
            tmp_path = Path(f.name)
            req_path = tmp_path.parent / "requirements.txt"
            shutil.move(tmp_path, req_path)
            
            parser = RequirementsParser()
            packages = parser.parse(req_path)
            
            assert len(packages) == 2
            package_names = {pkg.name for pkg in packages}
            assert "requests" in package_names
            assert "flask" in package_names
        finally:
            req_path.unlink(missing_ok=True)


class TestDockerfileParser:
    """Tests for DockerfileParser."""

    def test_can_parse_dockerfile(self, sample_dockerfile: Path):
        """Test that DockerfileParser can identify Dockerfile."""
        parser = DockerfileParser()
        assert parser.can_parse(sample_dockerfile)

    def test_cannot_parse_other_files(self, sample_yarn_lock: Path):
        """Test that DockerfileParser rejects non-Dockerfile files."""
        parser = DockerfileParser()
        assert not parser.can_parse(sample_yarn_lock)

    def test_parse_dockerfile(self, sample_dockerfile: Path):
        """Test parsing Dockerfile."""
        parser = DockerfileParser()
        packages = parser.parse(sample_dockerfile)
        
        # Verify packages were parsed
        assert len(packages) > 0
        
        # Verify package type (should be APT for Debian-based)
        for pkg in packages:
            assert pkg.package_type == PackageType.APT
        
        # Verify known packages exist
        package_names = {pkg.name for pkg in packages}
        assert "curl" in package_names
        assert "git" in package_names
        assert "wget" in package_names

    def test_parse_dockerfile_direct_dependencies(self, sample_dockerfile: Path):
        """Test that installed packages are marked as direct dependencies."""
        parser = DockerfileParser()
        packages = parser.parse(sample_dockerfile)
        
        # All explicitly installed packages should be direct dependencies
        for pkg in packages:
            if pkg.name in ["curl", "git", "wget"]:
                assert pkg.is_direct_dependency

    def test_get_dockerfile_info(self, sample_dockerfile: Path):
        """Test getting Dockerfile OS information."""
        parser = DockerfileParser()
        info = parser.get_dockerfile_info(sample_dockerfile)
        
        # Should detect Debian-based OS
        assert info.os_type == "debian"
