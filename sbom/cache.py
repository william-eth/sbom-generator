"""
Simple cache mechanism for storing fetched package information.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .models import LicenseInfo, RepoInfo


class Cache:
    """
    Simple file-based cache for package information.
    
    Stores repository URLs and license information to avoid
    repeated API calls for the same packages.
    """
    
    # Default cache file location
    DEFAULT_CACHE_FILE = "sbom_cache.json"
    
    # Default cache expiry (7 days)
    DEFAULT_EXPIRY_DAYS = 7
    
    def __init__(
        self,
        cache_file: Optional[str | Path] = None,
        expiry_days: int = DEFAULT_EXPIRY_DAYS,
        enabled: bool = True
    ):
        """
        Initialize cache.
        
        Args:
            cache_file: Path to cache file. Defaults to sbom_cache.json in script directory.
            expiry_days: Number of days before cache entries expire.
            enabled: Whether cache is enabled.
        """
        if cache_file is None:
            # Store cache in script directory
            script_dir = Path(__file__).parent.parent.resolve()
            cache_file = script_dir / self.DEFAULT_CACHE_FILE
        
        self.cache_file = Path(cache_file)
        self.expiry_days = expiry_days
        self.enabled = enabled
        self._cache: dict = {}
        self._dirty = False
        
        if self.enabled:
            self._load()
    
    def _load(self) -> None:
        """Load cache from file."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._cache = {}
    
    def _save(self) -> None:
        """Save cache to file."""
        if not self.enabled or not self._dirty:
            return
        
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
            self._dirty = False
        except IOError:
            pass
    
    def _is_expired(self, timestamp: str) -> bool:
        """Check if a cache entry is expired."""
        try:
            cached_time = datetime.fromisoformat(timestamp)
            expiry_time = cached_time + timedelta(days=self.expiry_days)
            return datetime.now() > expiry_time
        except (ValueError, TypeError):
            return True
    
    def _make_key(self, package_name: str, package_type: str) -> str:
        """Create cache key from package name and type."""
        return f"{package_type}:{package_name}"
    
    def get_repo_info(self, package_name: str, package_type: str) -> Optional[RepoInfo]:
        """
        Get cached repository info.
        
        Args:
            package_name: Name of the package.
            package_type: Type of package (npm or rubygems).
            
        Returns:
            Cached RepoInfo or None if not found/expired.
        """
        if not self.enabled:
            return None
        
        key = self._make_key(package_name, package_type)
        entry = self._cache.get(key)
        
        if entry and not self._is_expired(entry.get("timestamp", "")):
            repo_data = entry.get("repo_info")
            if repo_data:
                return RepoInfo(
                    url=repo_data.get("url", ""),
                    is_github=repo_data.get("is_github", False),
                    owner=repo_data.get("owner", ""),
                    repo=repo_data.get("repo", "")
                )
        
        return None
    
    def set_repo_info(self, package_name: str, package_type: str, repo_info: RepoInfo) -> None:
        """
        Cache repository info.
        
        Args:
            package_name: Name of the package.
            package_type: Type of package (npm or rubygems).
            repo_info: RepoInfo to cache.
        """
        if not self.enabled:
            return
        
        key = self._make_key(package_name, package_type)
        
        if key not in self._cache:
            self._cache[key] = {}
        
        self._cache[key]["repo_info"] = {
            "url": repo_info.url,
            "is_github": repo_info.is_github,
            "owner": repo_info.owner,
            "repo": repo_info.repo
        }
        self._cache[key]["timestamp"] = datetime.now().isoformat()
        self._dirty = True
    
    def get_license_info(self, owner: str, repo: str) -> Optional[LicenseInfo]:
        """
        Get cached license info.
        
        Args:
            owner: GitHub repository owner.
            repo: GitHub repository name.
            
        Returns:
            Cached LicenseInfo or None if not found/expired.
        """
        if not self.enabled:
            return None
        
        key = f"github:{owner}/{repo}"
        entry = self._cache.get(key)
        
        if entry and not self._is_expired(entry.get("timestamp", "")):
            license_data = entry.get("license_info")
            if license_data:
                return LicenseInfo(
                    name=license_data.get("name", ""),
                    spdx_id=license_data.get("spdx_id", ""),
                    url=license_data.get("url", ""),
                    content=license_data.get("content", ""),
                    is_standard=license_data.get("is_standard", True),
                    remark=license_data.get("remark", "")
                )
        
        return None
    
    def set_license_info(self, owner: str, repo: str, license_info: LicenseInfo) -> None:
        """
        Cache license info.
        
        Args:
            owner: GitHub repository owner.
            repo: GitHub repository name.
            license_info: LicenseInfo to cache.
        """
        if not self.enabled:
            return
        
        key = f"github:{owner}/{repo}"
        
        self._cache[key] = {
            "license_info": {
                "name": license_info.name,
                "spdx_id": license_info.spdx_id,
                "url": license_info.url,
                "content": license_info.content,
                "is_standard": license_info.is_standard,
                "remark": license_info.remark
            },
            "timestamp": datetime.now().isoformat()
        }
        self._dirty = True
    
    def get_source_package(self, binary_package: str) -> Optional[str]:
        """
        Get cached source package name for a Debian binary package.
        
        Args:
            binary_package: Name of the binary package.
            
        Returns:
            Cached source package name or None if not found/expired.
        """
        if not self.enabled:
            return None
        
        key = f"debian_source:{binary_package}"
        entry = self._cache.get(key)
        
        if entry and not self._is_expired(entry.get("timestamp", "")):
            return entry.get("source_package")
        
        return None
    
    def set_source_package(self, binary_package: str, source_package: str) -> None:
        """
        Cache source package name for a Debian binary package.
        
        Args:
            binary_package: Name of the binary package.
            source_package: Name of the source package.
        """
        if not self.enabled:
            return
        
        key = f"debian_source:{binary_package}"
        
        self._cache[key] = {
            "source_package": source_package,
            "timestamp": datetime.now().isoformat()
        }
        self._dirty = True
    
    def get_vcs_info(self, package_name: str) -> Optional[dict]:
        """
        Get cached VCS (Version Control System) info for a Debian package.
        
        Args:
            package_name: Name of the package.
            
        Returns:
            Cached VCS info dict or None if not found/expired.
        """
        if not self.enabled:
            return None
        
        key = f"debian_vcs:{package_name}"
        entry = self._cache.get(key)
        
        if entry and not self._is_expired(entry.get("timestamp", "")):
            vcs_data = entry.get("vcs_info")
            if vcs_data:
                return vcs_data
        
        return None
    
    def set_vcs_info(self, package_name: str, vcs_info: dict) -> None:
        """
        Cache VCS info for a Debian package.
        
        Args:
            package_name: Name of the package.
            vcs_info: VCS info dictionary with url, browser, type keys.
        """
        if not self.enabled:
            return
        
        key = f"debian_vcs:{package_name}"
        
        self._cache[key] = {
            "vcs_info": vcs_info,
            "timestamp": datetime.now().isoformat()
        }
        self._dirty = True
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache = {}
        self._dirty = True
        self._save()
        
        if self.cache_file.exists():
            try:
                self.cache_file.unlink()
            except IOError:
                pass
    
    def get_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics.
        """
        total = len(self._cache)
        expired = sum(
            1 for entry in self._cache.values()
            if self._is_expired(entry.get("timestamp", ""))
        )
        
        return {
            "total_entries": total,
            "valid_entries": total - expired,
            "expired_entries": expired,
            "cache_file": str(self.cache_file),
            "enabled": self.enabled
        }
    
    def save(self) -> None:
        """Explicitly save cache to file."""
        self._save()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._save()
        return False

