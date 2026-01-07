"""
GitHub API fetcher for license information.
"""

from typing import Optional

import requests

from ..models import LicenseInfo, RepoInfo


class GitHubFetcher:
    """Fetches license information from GitHub API."""
    
    GITHUB_API_URL = "https://api.github.com"
    TIMEOUT = 10
    
    def __init__(self, token: Optional[str] = None):
        """
        Initialize GitHub fetcher.
        
        Args:
            token: GitHub Personal Access Token (optional).
                   Without token: 60 requests/hour
                   With token: 5000 requests/hour
        """
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "SBOM-Script/1.0"
        })
        
        if token:
            self._session.headers["Authorization"] = f"token {token}"
        
        self._rate_limit_remaining: Optional[int] = None
    
    @property
    def rate_limit_remaining(self) -> Optional[int]:
        """Get remaining API rate limit."""
        return self._rate_limit_remaining
    
    def get_license_info(self, repo_info: RepoInfo) -> LicenseInfo:
        """
        Get license information for a GitHub repository.
        
        Args:
            repo_info: Repository information with owner and repo name.
            
        Returns:
            LicenseInfo object with license details.
            
        Raises:
            ValueError: If license information cannot be retrieved.
        """
        if not repo_info.is_github or not repo_info.owner or not repo_info.repo:
            raise ValueError("Not a valid GitHub repository")
        
        # Get license metadata and content in one flow
        return self._get_license_metadata(repo_info)
    
    def _get_license_metadata(self, repo_info: RepoInfo) -> LicenseInfo:
        """Get license metadata from GitHub repository API."""
        import base64
        
        # First, get repository info for default branch
        repo_url = f"{self.GITHUB_API_URL}/repos/{repo_info.owner}/{repo_info.repo}"
        
        try:
            response = self._session.get(repo_url, timeout=self.TIMEOUT)
            self._update_rate_limit(response)
            response.raise_for_status()
            
            repo_data = response.json()
            license_data = repo_data.get("license")
            
            if not license_data:
                return LicenseInfo(
                    name="No License",
                    remark="No license file found in repository"
                )
            
            default_branch = repo_data.get("default_branch", "main")
            
            # Get actual license file path and content from license API
            license_url = f"{self.GITHUB_API_URL}/repos/{repo_info.owner}/{repo_info.repo}/license"
            license_response = self._session.get(license_url, timeout=self.TIMEOUT)
            self._update_rate_limit(license_response)
            
            license_file_path = "LICENSE"  # Default fallback
            license_content = ""
            
            if license_response.status_code == 200:
                license_file_data = license_response.json()
                # Get the actual file path (e.g., "MIT-LICENSE", "LICENSE.md", "COPYING")
                license_file_path = license_file_data.get("path", "LICENSE")
                
                # Get license content (base64 encoded)
                content = license_file_data.get("content", "")
                encoding = license_file_data.get("encoding", "base64")
                
                if encoding == "base64" and content:
                    try:
                        license_content = base64.b64decode(content).decode("utf-8")
                    except (ValueError, UnicodeDecodeError):
                        license_content = ""
            
            # Construct the correct URL with actual license file name
            html_url = f"https://github.com/{repo_info.owner}/{repo_info.repo}/blob/{default_branch}/{license_file_path}"
            
            return LicenseInfo(
                name=license_data.get("name", "Unknown"),
                spdx_id=license_data.get("spdx_id", ""),
                url=html_url,
                content=license_content
            )
            
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                raise ValueError("Repository not found")
            elif e.response.status_code == 403:
                raise ValueError("API rate limit exceeded or access denied")
            else:
                raise ValueError(f"GitHub API error: {e}")
        except requests.RequestException as e:
            raise ValueError(f"Failed to fetch from GitHub: {e}")
    
    def _update_rate_limit(self, response: requests.Response) -> None:
        """Update rate limit from response headers."""
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining:
            try:
                self._rate_limit_remaining = int(remaining)
            except ValueError:
                pass
    
    def check_rate_limit(self) -> dict:
        """
        Check current API rate limit status.
        
        Returns:
            Dict with 'limit', 'remaining', and 'reset' (Unix timestamp).
        """
        url = f"{self.GITHUB_API_URL}/rate_limit"
        
        try:
            response = self._session.get(url, timeout=self.TIMEOUT)
            response.raise_for_status()
            data = response.json()
            
            core = data.get("resources", {}).get("core", {})
            return {
                "limit": core.get("limit", 0),
                "remaining": core.get("remaining", 0),
                "reset": core.get("reset", 0)
            }
        except requests.RequestException:
            return {"limit": 0, "remaining": 0, "reset": 0}
    
    def close(self):
        """Close the HTTP session."""
        self._session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

