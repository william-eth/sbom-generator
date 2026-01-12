"""
Tests for SBOM data models.
"""

import pytest

from sbom.models import (
    Package,
    PackageType,
    RepoInfo,
    LicenseInfo,
    SBOMCategory,
    SBOMEntry,
    ProcessingError,
)


class TestPackageType:
    """Tests for PackageType enum."""

    def test_npm_category(self):
        """Test NPM package type category."""
        assert PackageType.NPM.category == SBOMCategory.APPLICATION

    def test_rubygems_category(self):
        """Test RUBYGEMS package type category."""
        assert PackageType.RUBYGEMS.category == SBOMCategory.APPLICATION

    def test_pypi_category(self):
        """Test PYPI package type category."""
        assert PackageType.PYPI.category == SBOMCategory.APPLICATION

    def test_apt_category(self):
        """Test APT package type category."""
        assert PackageType.APT.category == SBOMCategory.OS_SYSTEM

    def test_apk_category(self):
        """Test APK package type category."""
        assert PackageType.APK.category == SBOMCategory.OS_SYSTEM


class TestPackage:
    """Tests for Package dataclass."""

    def test_package_creation(self):
        """Test creating a Package instance."""
        pkg = Package(
            name="express",
            version="4.18.2",
            package_type=PackageType.NPM,
        )
        assert pkg.name == "express"
        assert pkg.version == "4.18.2"
        assert pkg.package_type == PackageType.NPM
        assert pkg.dependencies == []
        assert pkg.is_direct_dependency is False

    def test_package_with_dependencies(self):
        """Test creating a Package with dependencies."""
        pkg = Package(
            name="express",
            version="4.18.2",
            package_type=PackageType.NPM,
            dependencies=["accepts", "body-parser"],
            is_direct_dependency=True,
        )
        assert len(pkg.dependencies) == 2
        assert "accepts" in pkg.dependencies
        assert pkg.is_direct_dependency is True

    def test_package_equality(self):
        """Test Package equality based on name and version."""
        pkg1 = Package(name="express", version="4.18.2", package_type=PackageType.NPM)
        pkg2 = Package(name="express", version="4.18.2", package_type=PackageType.NPM)
        pkg3 = Package(name="express", version="4.17.0", package_type=PackageType.NPM)
        
        assert pkg1 == pkg2
        assert pkg1 != pkg3

    def test_package_hash(self):
        """Test Package hash for use in sets/dicts."""
        pkg1 = Package(name="express", version="4.18.2", package_type=PackageType.NPM)
        pkg2 = Package(name="express", version="4.18.2", package_type=PackageType.NPM)
        
        # Should be usable in sets
        pkg_set = {pkg1, pkg2}
        assert len(pkg_set) == 1


class TestRepoInfo:
    """Tests for RepoInfo dataclass."""

    def test_repo_info_creation(self):
        """Test creating a RepoInfo instance."""
        repo = RepoInfo(url="https://github.com/expressjs/express")
        assert repo.url == "https://github.com/expressjs/express"
        assert repo.is_github is False
        assert repo.owner == ""
        assert repo.repo == ""

    def test_from_github_url_https(self):
        """Test creating RepoInfo from HTTPS GitHub URL."""
        repo = RepoInfo.from_github_url("https://github.com/expressjs/express")
        assert repo.is_github is True
        assert repo.owner == "expressjs"
        assert repo.repo == "express"
        assert repo.url == "https://github.com/expressjs/express"

    def test_from_github_url_with_git_suffix(self):
        """Test creating RepoInfo from GitHub URL with .git suffix."""
        repo = RepoInfo.from_github_url("https://github.com/expressjs/express.git")
        assert repo.is_github is True
        assert repo.owner == "expressjs"
        assert repo.repo == "express"

    def test_from_github_url_git_protocol(self):
        """Test creating RepoInfo from git:// protocol URL."""
        repo = RepoInfo.from_github_url("git://github.com/expressjs/express")
        assert repo.is_github is True
        assert repo.owner == "expressjs"
        assert repo.repo == "express"

    def test_from_github_url_git_plus_https(self):
        """Test creating RepoInfo from git+https:// URL."""
        repo = RepoInfo.from_github_url("git+https://github.com/expressjs/express.git")
        assert repo.is_github is True
        assert repo.owner == "expressjs"
        assert repo.repo == "express"

    def test_from_non_github_url(self):
        """Test creating RepoInfo from non-GitHub URL."""
        repo = RepoInfo.from_github_url("https://gitlab.com/user/repo")
        assert repo.is_github is False
        assert repo.url == "https://gitlab.com/user/repo"


class TestLicenseInfo:
    """Tests for LicenseInfo dataclass."""

    def test_license_info_creation(self):
        """Test creating a LicenseInfo instance."""
        license_info = LicenseInfo(
            name="MIT License",
            spdx_id="MIT",
            url="https://github.com/expressjs/express/blob/master/LICENSE",
        )
        assert license_info.name == "MIT License"
        assert license_info.spdx_id == "MIT"
        assert license_info.is_standard is True

    def test_license_info_defaults(self):
        """Test LicenseInfo default values."""
        license_info = LicenseInfo()
        assert license_info.name == ""
        assert license_info.spdx_id == ""
        assert license_info.url == ""
        assert license_info.content == ""
        assert license_info.is_standard is True
        assert license_info.remark == ""


class TestSBOMEntry:
    """Tests for SBOMEntry dataclass."""

    def test_sbom_entry_creation(self):
        """Test creating an SBOMEntry instance."""
        entry = SBOMEntry(
            package_name="express",
            referenced_by="[直接依賴]",
            repo_url="https://github.com/expressjs/express",
            license_name="MIT License",
            license_url="https://github.com/expressjs/express/blob/master/LICENSE",
        )
        assert entry.package_name == "express"
        assert entry.referenced_by == "[直接依賴]"
        assert entry.remark == ""
        assert entry.vcs_url == ""


class TestProcessingError:
    """Tests for ProcessingError dataclass."""

    def test_processing_error_creation(self):
        """Test creating a ProcessingError instance."""
        error = ProcessingError(
            package_name="unknown-package",
            reason="Package not found in registry",
        )
        assert error.package_name == "unknown-package"
        assert error.reason == "Package not found in registry"
