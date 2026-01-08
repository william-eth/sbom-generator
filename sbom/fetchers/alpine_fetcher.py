"""
Fetcher for Alpine Linux package information and licenses.
Uses Alpine packages database and GitLab aports repository.
"""

import re
from typing import Optional

import requests

from .base_fetcher import BaseLicenseFetcher
from ..models import LicenseInfo, PackageType


class AlpineFetcher(BaseLicenseFetcher):
    """Fetches license information from Alpine Linux package repositories."""
    
    # API/URL endpoints
    PACKAGES_URL = "https://pkgs.alpinelinux.org/package"
    APORTS_GITLAB_URL = "https://gitlab.alpinelinux.org/alpine/aports"
    APORTS_RAW_URL = "https://gitlab.alpinelinux.org/alpine/aports/-/raw/master"
    
    # Alpine branches to search (in order of preference)
    BRANCHES = ["edge", "v3.21", "v3.20", "v3.19"]
    
    # Alpine repositories
    REPOS = ["main", "community", "testing"]
    
    # Common SPDX license identifiers used in Alpine
    LICENSE_MAPPINGS = {
        "mit": "MIT",
        "gpl": "GPL",
        "gpl2": "GPL-2.0",
        "gpl-2.0": "GPL-2.0",
        "gpl-2.0+": "GPL-2.0-or-later",
        "gpl-2.0-only": "GPL-2.0-only",
        "gpl-2.0-or-later": "GPL-2.0-or-later",
        "gpl3": "GPL-3.0",
        "gpl-3.0": "GPL-3.0",
        "gpl-3.0+": "GPL-3.0-or-later",
        "gpl-3.0-only": "GPL-3.0-only",
        "gpl-3.0-or-later": "GPL-3.0-or-later",
        "lgpl": "LGPL",
        "lgpl-2.0": "LGPL-2.0",
        "lgpl-2.1": "LGPL-2.1",
        "lgpl-3.0": "LGPL-3.0",
        "bsd": "BSD",
        "bsd-2-clause": "BSD-2-Clause",
        "bsd-3-clause": "BSD-3-Clause",
        "apache": "Apache",
        "apache-2.0": "Apache-2.0",
        "mpl-2.0": "MPL-2.0",
        "isc": "ISC",
        "zlib": "Zlib",
        "public-domain": "Public Domain",
        "unlicense": "Unlicense",
        "cc0-1.0": "CC0-1.0",
        "wtfpl": "WTFPL",
        "artistic-2.0": "Artistic-2.0",
    }
    
    TIMEOUT = 10
    
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json, text/html",
            "User-Agent": "SBOM-Script/1.0"
        })
        # Cache for found package locations
        self._package_locations: dict[str, dict] = {}
    
    @property
    def supported_package_types(self) -> list[PackageType]:
        return [PackageType.APK]
    
    def get_license_info(self, package_name: str, package_type: PackageType) -> LicenseInfo:
        """
        Get license information for an Alpine package.
        
        Tries to fetch APKBUILD file from aports repository to extract license.
        """
        if package_type != PackageType.APK:
            return LicenseInfo(remark="Unsupported package type for Alpine fetcher")
        
        # Find package location in aports
        location = self._find_package_location(package_name)
        
        if not location:
            return LicenseInfo(
                name="Unknown",
                url=f"{self.PACKAGES_URL}/edge/main/x86_64/{package_name}",
                remark="Package not found in Alpine repositories"
            )
        
        # Try to fetch APKBUILD and extract license
        license_info = self._fetch_license_from_apkbuild(package_name, location)
        
        if license_info:
            return license_info
        
        # Fallback
        return LicenseInfo(
            name="See Alpine Package",
            url=self._get_package_page_url(package_name, location),
            remark="License info available on Alpine packages"
        )
    
    def get_package_url(self, package_name: str, package_type: PackageType) -> str:
        """Get the Alpine packages URL for the package."""
        location = self._find_package_location(package_name)
        if location:
            return self._get_package_page_url(package_name, location)
        return f"{self.PACKAGES_URL}/edge/main/x86_64/{package_name}"
    
    def _find_package_location(self, package_name: str) -> Optional[dict]:
        """Find which branch and repo contains the package."""
        # Check cache first
        if package_name in self._package_locations:
            return self._package_locations[package_name]
        
        # Search through branches and repos
        for branch in self.BRANCHES:
            for repo in self.REPOS:
                url = f"{self.PACKAGES_URL}/{branch}/{repo}/x86_64/{package_name}"
                try:
                    response = self._session.head(url, timeout=self.TIMEOUT, allow_redirects=True)
                    if response.status_code == 200:
                        location = {"branch": branch, "repo": repo}
                        self._package_locations[package_name] = location
                        return location
                except requests.RequestException:
                    continue
        
        return None
    
    def _get_package_page_url(self, package_name: str, location: dict) -> str:
        """Get the package page URL."""
        return f"{self.PACKAGES_URL}/{location['branch']}/{location['repo']}/x86_64/{package_name}"
    
    def _fetch_license_from_apkbuild(
        self,
        package_name: str,
        location: dict
    ) -> Optional[LicenseInfo]:
        """Fetch and parse APKBUILD file to extract license."""
        repo = location["repo"]
        
        # APKBUILD URL in aports repository
        apkbuild_url = f"{self.APORTS_RAW_URL}/{repo}/{package_name}/APKBUILD"
        
        try:
            response = self._session.get(apkbuild_url, timeout=self.TIMEOUT)
            
            if response.status_code != 200:
                # Package might be a subpackage, try to find parent
                return None
            
            content = response.text
            
            # Parse license from APKBUILD
            license_name = self._parse_license_from_apkbuild(content)
            
            # Get source URL if available
            source_url = self._parse_source_url_from_apkbuild(content)
            
            aports_url = f"{self.APORTS_GITLAB_URL}/-/blob/master/{repo}/{package_name}/APKBUILD"
            
            return LicenseInfo(
                name=license_name or "See APKBUILD",
                url=aports_url,
                remark=f"Source: {source_url}" if source_url else ""
            )
            
        except requests.RequestException:
            return None
    
    def _parse_license_from_apkbuild(self, content: str) -> Optional[str]:
        """Parse license from APKBUILD content."""
        # Match: license="MIT" or license='GPL-3.0-or-later'
        license_pattern = re.compile(r'^license=["\']([^"\']+)["\']', re.MULTILINE)
        match = license_pattern.search(content)
        
        if match:
            license_str = match.group(1).strip()
            # Handle multiple licenses (e.g., "MIT AND Apache-2.0")
            # Normalize common variations
            license_lower = license_str.lower()
            
            # Check for exact match in mappings
            if license_lower in self.LICENSE_MAPPINGS:
                return self.LICENSE_MAPPINGS[license_lower]
            
            # Return as-is if it looks like a valid SPDX identifier
            if re.match(r'^[A-Za-z0-9.\-+ ]+$', license_str):
                return license_str
            
            return license_str
        
        return None
    
    def _parse_source_url_from_apkbuild(self, content: str) -> Optional[str]:
        """Parse source URL from APKBUILD content."""
        # Match: url="https://..." or url='https://...'
        url_pattern = re.compile(r'^url=["\']([^"\']+)["\']', re.MULTILINE)
        match = url_pattern.search(content)
        
        if match:
            return match.group(1).strip()
        
        return None
    
    def close(self):
        """Close the HTTP session."""
        self._session.close()
