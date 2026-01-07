"""
Data models for SBOM script.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PackageType(Enum):
    """Type of package based on the lock file source."""
    NPM = "npm"           # From yarn.lock or package-lock.json
    RUBYGEMS = "rubygems" # From Gemfile.lock


@dataclass
class Package:
    """Represents a package from a lock file."""
    name: str
    version: str
    package_type: PackageType
    dependencies: list[str] = field(default_factory=list)
    is_direct_dependency: bool = False
    
    def __hash__(self):
        return hash((self.name, self.version))
    
    def __eq__(self, other):
        if not isinstance(other, Package):
            return False
        return self.name == other.name and self.version == other.version


@dataclass
class RepoInfo:
    """Repository information for a package."""
    url: str
    is_github: bool = False
    owner: str = ""
    repo: str = ""
    
    @classmethod
    def from_github_url(cls, url: str) -> "RepoInfo":
        """Create RepoInfo from a GitHub URL."""
        # Normalize URL
        url = url.rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]
        
        # Extract owner and repo
        # Handles: https://github.com/owner/repo
        #          git://github.com/owner/repo
        #          git+https://github.com/owner/repo
        #          ssh://git@github.com/owner/repo
        parts = url.replace("git+", "").replace("git://", "https://")
        parts = parts.replace("ssh://git@", "https://")
        parts = parts.replace("git@github.com:", "https://github.com/")
        
        if "github.com" in parts:
            try:
                path_parts = parts.split("github.com/")[1].split("/")
                if len(path_parts) >= 2:
                    return cls(
                        url=f"https://github.com/{path_parts[0]}/{path_parts[1]}",
                        is_github=True,
                        owner=path_parts[0],
                        repo=path_parts[1]
                    )
            except (IndexError, ValueError):
                pass
        
        return cls(url=url, is_github=False)


@dataclass
class LicenseInfo:
    """License information for a package."""
    name: str = ""
    spdx_id: str = ""
    url: str = ""
    content: str = ""
    is_standard: bool = True
    remark: str = ""


@dataclass
class SBOMEntry:
    """A single entry in the SBOM report."""
    package_name: str
    referenced_by: str  # Comma-separated list of packages that reference this package
    repo_url: str
    license_name: str
    license_url: str
    remark: str = ""


@dataclass
class ProcessingError:
    """Error information when processing a package fails."""
    package_name: str
    reason: str

