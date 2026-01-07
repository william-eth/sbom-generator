"""
Fetcher for package registry information (npm, RubyGems).
Used to retrieve repository URLs for packages.
"""

import re
from typing import Optional

import requests

from ..models import PackageType, RepoInfo


class RegistryFetcher:
    """Fetches package information from package registries."""
    
    # API endpoints
    NPM_REGISTRY_URL = "https://registry.npmjs.org"
    RUBYGEMS_API_URL = "https://rubygems.org/api/v1/gems"
    
    # Request timeout in seconds
    TIMEOUT = 10
    
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json",
            "User-Agent": "SBOM-Script/1.0"
        })
    
    def get_repo_info(self, package_name: str, package_type: PackageType) -> RepoInfo:
        """
        Get repository information for a package.
        
        Args:
            package_name: Name of the package.
            package_type: Type of package (NPM or RUBYGEMS).
            
        Returns:
            RepoInfo object with repository URL and metadata.
            
        Raises:
            ValueError: If package information cannot be retrieved.
        """
        if package_type == PackageType.NPM:
            return self._get_npm_repo_info(package_name)
        elif package_type == PackageType.RUBYGEMS:
            return self._get_rubygems_repo_info(package_name)
        else:
            raise ValueError(f"Unsupported package type: {package_type}")
    
    def _get_npm_repo_info(self, package_name: str) -> RepoInfo:
        """Get repository info from npm registry."""
        # Handle scoped packages (@scope/name)
        encoded_name = package_name.replace("/", "%2F")
        url = f"{self.NPM_REGISTRY_URL}/{encoded_name}"
        
        try:
            response = self._session.get(url, timeout=self.TIMEOUT)
            response.raise_for_status()
            data = response.json()
            
            # Try to get repository URL from various fields
            repo_url = self._extract_npm_repo_url(data)
            
            if repo_url:
                return RepoInfo.from_github_url(repo_url)
            
            # Fallback to homepage
            homepage = data.get("homepage", "")
            if homepage:
                return RepoInfo.from_github_url(homepage)
            
            # No repository found
            return RepoInfo(url="", is_github=False)
            
        except requests.RequestException as e:
            raise ValueError(f"Failed to fetch npm package info: {e}")
    
    def _extract_npm_repo_url(self, data: dict) -> Optional[str]:
        """Extract repository URL from npm package data."""
        # Try repository field
        repository = data.get("repository")
        if repository:
            if isinstance(repository, str):
                return repository
            elif isinstance(repository, dict):
                repo_url = repository.get("url", "")
                if repo_url:
                    return repo_url
        
        # Try bugs field (often has GitHub URL)
        bugs = data.get("bugs")
        if bugs:
            if isinstance(bugs, str):
                return bugs
            elif isinstance(bugs, dict):
                bugs_url = bugs.get("url", "")
                if "github.com" in bugs_url:
                    # Convert issues URL to repo URL
                    # https://github.com/owner/repo/issues -> https://github.com/owner/repo
                    return re.sub(r'/issues/?$', '', bugs_url)
        
        return None
    
    def _get_rubygems_repo_info(self, package_name: str) -> RepoInfo:
        """Get repository info from RubyGems API."""
        url = f"{self.RUBYGEMS_API_URL}/{package_name}.json"
        
        try:
            response = self._session.get(url, timeout=self.TIMEOUT)
            response.raise_for_status()
            data = response.json()
            
            # Try various URL fields in order of preference
            for field in ("source_code_uri", "homepage_uri", "project_uri"):
                uri = data.get(field, "")
                if uri and "github.com" in uri:
                    return RepoInfo.from_github_url(uri)
            
            # Try metadata field
            metadata = data.get("metadata", {})
            if metadata:
                for field in ("source_code_uri", "github_repo", 
                             "homepage_uri", "bug_tracker_uri"):
                    uri = metadata.get(field, "")
                    if uri and "github.com" in uri:
                        return RepoInfo.from_github_url(uri)
            
            # Return any available URL
            for field in ("source_code_uri", "homepage_uri", "project_uri"):
                uri = data.get(field, "")
                if uri:
                    return RepoInfo.from_github_url(uri)
            
            # No repository found
            return RepoInfo(url="", is_github=False)
            
        except requests.RequestException as e:
            raise ValueError(f"Failed to fetch RubyGems package info: {e}")
    
    def close(self):
        """Close the HTTP session."""
        self._session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

