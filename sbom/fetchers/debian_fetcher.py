"""
Fetcher for Debian/Ubuntu package information and licenses.
Uses official Debian APIs:
  - Debian Sources API (https://sources.debian.org/api/)
  - Debian Metadata FTP (https://metadata.ftp-master.debian.org/)
  - Debian Tracker API (https://tracker.debian.org/)
  - Debian UDD (Ultimate Debian Database) for binary→source mapping

Reference flow:
1. Query binary→source mapping if needed
2. Query Sources API for package info and version
3. Fetch copyright file from metadata.ftp-master.debian.org
4. Get VCS (Salsa GitLab) info from tracker API
"""

import re
from dataclasses import dataclass, field
from typing import Optional

import requests

from .base_fetcher import BaseLicenseFetcher
from ..models import LicenseInfo, PackageType


@dataclass
class DebianPackageInfo:
    """Detailed information about a Debian package."""
    name: str
    version: str = ""
    suite: str = ""  # e.g., trixie, bookworm, sid
    copyright_url: str = ""
    tracker_url: str = ""
    vcs_url: str = ""  # Salsa GitLab URL
    vcs_browser: str = ""  # VCS browser URL
    source_package: str = ""  # Source package name (may differ from binary)
    homepage: str = ""


class DebianFetcher(BaseLicenseFetcher):
    """
    Fetches license information from Debian package repositories.
    
    Uses official APIs instead of web scraping:
    - sources.debian.org/api/ - Package metadata and source info
    - metadata.ftp-master.debian.org - Copyright files
    - tracker.debian.org/api/ - Package tracking, VCS info, binary→source mapping
    """
    
    # Official API endpoints
    SOURCES_API_URL = "https://sources.debian.org/api/src"
    METADATA_FTP_URL = "https://metadata.ftp-master.debian.org/changelogs"
    TRACKER_URL = "https://tracker.debian.org/pkg"
    PACKAGES_URL = "https://packages.debian.org"
    
    # Snapshot API for binary→source mapping
    # https://snapshot.debian.org/
    SNAPSHOT_API_URL = "https://snapshot.debian.org/mr/binary"
    
    # Common license mappings for Debian packages
    LICENSE_MAPPINGS = {
        "gpl": "GPL",
        "gpl-2": "GPL-2.0",
        "gpl-2+": "GPL-2.0-or-later",
        "gpl-2.0": "GPL-2.0",
        "gpl-2.0+": "GPL-2.0-or-later",
        "gpl-3": "GPL-3.0",
        "gpl-3+": "GPL-3.0-or-later",
        "gpl-3.0": "GPL-3.0",
        "gpl-3.0+": "GPL-3.0-or-later",
        "lgpl": "LGPL",
        "lgpl-2": "LGPL-2.0",
        "lgpl-2.0": "LGPL-2.0",
        "lgpl-2.1": "LGPL-2.1",
        "lgpl-2.1+": "LGPL-2.1-or-later",
        "lgpl-3": "LGPL-3.0",
        "lgpl-3.0": "LGPL-3.0",
        "mit": "MIT",
        "expat": "MIT",
        "bsd": "BSD",
        "bsd-2-clause": "BSD-2-Clause",
        "bsd-3-clause": "BSD-3-Clause",
        "apache": "Apache",
        "apache-2": "Apache-2.0",
        "apache-2.0": "Apache-2.0",
        "artistic": "Artistic",
        "artistic-2": "Artistic-2.0",
        "public-domain": "Public Domain",
        "isc": "ISC",
        "zlib": "Zlib",
        "mpl": "MPL",
        "mpl-2": "MPL-2.0",
        "mpl-2.0": "MPL-2.0",
        "cc0": "CC0-1.0",
        "cc0-1.0": "CC0-1.0",
        "unlicense": "Unlicense",
        "wtfpl": "WTFPL",
        "postgresql": "PostgreSQL",
    }
    
    TIMEOUT = 15
    
    def __init__(self, cache=None):
        """
        Initialize Debian fetcher.
        
        Args:
            cache: Optional Cache instance for persistent caching of
                   source package mappings and VCS info.
        """
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json, text/plain",
            "User-Agent": "SBOM-Generator/1.0 (Debian Package License Fetcher)"
        })
        # External cache for persistent storage
        self._external_cache = cache
        # In-memory cache for binary→source mappings (session only)
        self._source_package_cache: dict[str, str] = {}
        # In-memory cache for VCS URLs (session only)
        self._vcs_cache: dict[str, dict] = {}
    
    @property
    def supported_package_types(self) -> list[PackageType]:
        return [PackageType.APT]
    
    def get_license_info(self, package_name: str, package_type: PackageType) -> LicenseInfo:
        """
        Get license information for a Debian package.
        
        Flow:
        1. Find source package name (binary→source mapping)
        2. Query Sources API for package metadata
        3. Fetch copyright file from metadata.ftp-master.debian.org
        4. Get VCS URL from tracker API
        5. Parse license from copyright file
        """
        if package_type != PackageType.APT:
            return LicenseInfo(remark="Unsupported package type for Debian fetcher")
        
        # Step 1: Find source package name
        source_package = self._find_source_package(package_name)
        
        # Step 2: Get package info from Sources API
        pkg_info = self._get_package_info(source_package or package_name)
        
        if not pkg_info:
            # Try with original name if source lookup failed
            if source_package and source_package != package_name:
                pkg_info = self._get_package_info(package_name)
        
        if not pkg_info:
            # Fallback: return tracker URL
            return LicenseInfo(
                name="See Debian Package",
                url=f"{self.TRACKER_URL}/{package_name}",
                remark="Package not found in Debian sources"
            )
        
        # Step 3: Get VCS info from tracker API
        vcs_info = self._get_vcs_info(pkg_info.source_package or package_name)
        if vcs_info:
            pkg_info.vcs_url = vcs_info.get("url", "")
            pkg_info.vcs_browser = vcs_info.get("browser", "")
        
        # Step 4: Try to fetch copyright file from metadata.ftp-master.debian.org
        license_info = self._fetch_copyright_from_metadata(pkg_info)
        
        if license_info:
            # Add VCS info to remark
            self._add_vcs_to_remark(license_info, pkg_info)
            return license_info
        
        # Step 5: Fallback to sources.debian.org copyright
        license_info = self._fetch_copyright_from_sources(pkg_info)
        
        if license_info:
            self._add_vcs_to_remark(license_info, pkg_info)
            return license_info
        
        # Final fallback with VCS info
        vcs_remark = self._format_vcs_remark(pkg_info)
        return LicenseInfo(
            name="See Debian Package",
            url=pkg_info.tracker_url or f"{self.TRACKER_URL}/{package_name}",
            remark=vcs_remark or "License info available on Debian tracker"
        )
    
    def get_package_url(self, package_name: str, package_type: PackageType) -> str:
        """Get the Debian tracker URL for the package."""
        return f"{self.TRACKER_URL}/{package_name}"
    
    def _find_source_package(self, binary_package: str) -> Optional[str]:
        """
        Find the source package name for a binary package.
        
        Uses cached values first (external cache → in-memory cache),
        then queries tracker API.
        """
        # Check in-memory cache first
        if binary_package in self._source_package_cache:
            return self._source_package_cache[binary_package]
        
        # Check external persistent cache
        if self._external_cache:
            cached_source = self._external_cache.get_source_package(binary_package)
            if cached_source:
                self._source_package_cache[binary_package] = cached_source
                return cached_source
        
        # Query tracker API to get source package info
        source = self._query_tracker_for_source(binary_package)
        
        if source:
            # Save to both caches
            self._source_package_cache[binary_package] = source
            if self._external_cache:
                self._external_cache.set_source_package(binary_package, source)
            return source
        
        # If not found, cache the original name
        self._source_package_cache[binary_package] = binary_package
        if self._external_cache:
            self._external_cache.set_source_package(binary_package, binary_package)
        return binary_package
    
    def _query_tracker_for_source(self, package_name: str) -> Optional[str]:
        """
        Query Debian Snapshot API to find source package for a binary package.
        
        API: https://snapshot.debian.org/mr/binary/{binary_package}/
        
        Returns the source package name that provides the binary package.
        """
        # First, check if it's already a source package in sources.debian.org
        sources_url = f"{self.SOURCES_API_URL}/{package_name}"
        try:
            response = self._session.get(sources_url, timeout=self.TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                if data.get("package"):
                    # It's a valid source package
                    return package_name
        except (requests.RequestException, ValueError):
            pass
        
        # Query snapshot API for binary→source mapping
        snapshot_url = f"{self.SNAPSHOT_API_URL}/{package_name}/"
        
        try:
            response = self._session.get(snapshot_url, timeout=self.TIMEOUT)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            # Get results and find the source package
            results = data.get("result", [])
            if results and isinstance(results, list):
                # Get the first (latest) result
                latest = results[0]
                source = latest.get("source")
                if source:
                    return source
            
        except requests.RequestException:
            pass
        except (ValueError, KeyError):
            pass
        
        return None
    
    def _get_vcs_info(self, package_name: str) -> Optional[dict]:
        """
        Get VCS (Version Control System) info from debian/control file.
        
        Parses Vcs-Git and Vcs-Browser fields from the source package's
        debian/control file via sources.debian.org.
        
        Returns Salsa GitLab or other VCS URLs.
        """
        # Check in-memory cache first
        if package_name in self._vcs_cache:
            return self._vcs_cache[package_name]
        
        # Check external persistent cache
        if self._external_cache:
            cached_vcs = self._external_cache.get_vcs_info(package_name)
            if cached_vcs:
                self._vcs_cache[package_name] = cached_vcs
                return cached_vcs
        
        # Get package info to find latest version
        pkg_info = self._get_package_info(package_name)
        if not pkg_info or not pkg_info.version:
            return None
        
        # Fetch debian/control file from sources.debian.org
        control_url = f"https://sources.debian.org/data{self._get_package_path(package_name)}/{pkg_info.version}/debian/control"
        
        try:
            response = self._session.get(control_url, timeout=self.TIMEOUT)
            
            if response.status_code != 200:
                return None
            
            content = response.text
            vcs_info = self._parse_vcs_from_control(content)
            
            # Cache the result if found
            if vcs_info:
                self._vcs_cache[package_name] = vcs_info
                if self._external_cache:
                    self._external_cache.set_vcs_info(package_name, vcs_info)
                return vcs_info
            
        except requests.RequestException:
            pass
        
        return None
    
    def _parse_vcs_from_control(self, content: str) -> Optional[dict]:
        """
        Parse VCS information from debian/control file content.
        
        Looks for:
        - Vcs-Git: https://salsa.debian.org/...
        - Vcs-Browser: https://salsa.debian.org/...
        """
        vcs_info = {}
        
        # Parse Vcs-Git field
        vcs_git_pattern = re.compile(r'^Vcs-Git:\s*(.+)$', re.MULTILINE | re.IGNORECASE)
        match = vcs_git_pattern.search(content)
        if match:
            vcs_info["url"] = match.group(1).strip()
        
        # Parse Vcs-Browser field
        vcs_browser_pattern = re.compile(r'^Vcs-Browser:\s*(.+)$', re.MULTILINE | re.IGNORECASE)
        match = vcs_browser_pattern.search(content)
        if match:
            vcs_info["browser"] = match.group(1).strip()
        
        # If we have a Git URL but no browser, construct one for Salsa
        if vcs_info.get("url") and not vcs_info.get("browser"):
            git_url = vcs_info["url"]
            if "salsa.debian.org" in git_url:
                # Convert git URL to browser URL
                browser_url = git_url.replace(".git", "").replace("git@salsa.debian.org:", "https://salsa.debian.org/")
                vcs_info["browser"] = browser_url
        
        return vcs_info if vcs_info else None
    
    def _add_vcs_to_remark(self, license_info: LicenseInfo, pkg_info: DebianPackageInfo) -> None:
        """Add VCS information to the license info remark."""
        vcs_remark = self._format_vcs_remark(pkg_info)
        if vcs_remark:
            if license_info.remark:
                license_info.remark = f"{license_info.remark} | {vcs_remark}"
            else:
                license_info.remark = vcs_remark
    
    def _format_vcs_remark(self, pkg_info: DebianPackageInfo) -> str:
        """Format VCS info for remark field."""
        if pkg_info.vcs_browser:
            return f"VCS: {pkg_info.vcs_browser}"
        elif pkg_info.vcs_url:
            return f"VCS: {pkg_info.vcs_url}"
        return ""
    
    def _get_package_info(self, package_name: str) -> Optional[DebianPackageInfo]:
        """
        Get package information from Debian Sources API.
        
        API: https://sources.debian.org/api/src/{package}/
        """
        url = f"{self.SOURCES_API_URL}/{package_name}"
        
        try:
            response = self._session.get(url, timeout=self.TIMEOUT)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            if not data.get("package"):
                return None
            
            pkg_info = DebianPackageInfo(
                name=package_name,
                source_package=data.get("package", package_name),
                tracker_url=f"{self.TRACKER_URL}/{package_name}"
            )
            
            # Get latest version info
            versions = data.get("versions", [])
            if versions:
                latest = versions[0] if isinstance(versions[0], dict) else {}
                pkg_info.version = latest.get("version", "")
                suites = latest.get("suites", [])
                pkg_info.suite = suites[0] if suites else "sid"
            
            return pkg_info
            
        except requests.RequestException:
            return None
        except (ValueError, KeyError):
            return None
    
    def _get_package_path(self, package_name: str) -> str:
        """
        Get the Debian pool path for a package.
        
        Debian uses a specific directory structure:
        - lib* packages: /main/lib{x}/{package}/ where x is the 4th character
        - other packages: /main/{first_letter}/{package}/
        
        Examples:
        - libreoffice -> /main/libr/libreoffice/
        - curl -> /main/c/curl/
        - build-essential -> /main/b/build-essential/
        """
        if package_name.startswith("lib") and len(package_name) > 3:
            prefix = package_name[:4]
        else:
            prefix = package_name[0]
        
        return f"/main/{prefix}/{package_name}"
    
    def _fetch_copyright_from_metadata(
        self,
        pkg_info: DebianPackageInfo
    ) -> Optional[LicenseInfo]:
        """
        Fetch copyright file from metadata.ftp-master.debian.org.
        
        URL format:
        https://metadata.ftp-master.debian.org/changelogs/main/{prefix}/{package}/{package}_{version}_copyright
        """
        if not pkg_info.version:
            return None
        
        package_path = self._get_package_path(pkg_info.source_package or pkg_info.name)
        package_name = pkg_info.source_package or pkg_info.name
        
        copyright_url = f"{self.METADATA_FTP_URL}{package_path}/{package_name}_{pkg_info.version}_copyright"
        
        try:
            response = self._session.get(copyright_url, timeout=self.TIMEOUT)
            
            if response.status_code != 200:
                return None
            
            content = response.text
            
            if not content or len(content) < 10:
                return None
            
            license_name = self._parse_license_from_copyright(content)
            
            return LicenseInfo(
                name=license_name or "See Copyright File",
                url=copyright_url,
                content=content[:2000] if content else "",
                remark=""
            )
            
        except requests.RequestException:
            return None
    
    def _fetch_copyright_from_sources(
        self,
        pkg_info: DebianPackageInfo
    ) -> Optional[LicenseInfo]:
        """
        Fetch copyright file from sources.debian.org API.
        """
        if not pkg_info.version:
            return None
        
        package_name = pkg_info.source_package or pkg_info.name
        url = f"{self.SOURCES_API_URL}/{package_name}/{pkg_info.version}/debian/copyright/"
        
        try:
            response = self._session.get(url, timeout=self.TIMEOUT)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            content = ""
            
            if "content" in data:
                content = data.get("content", "")
            
            if not content:
                raw_url = data.get("raw_url", "")
                if raw_url:
                    raw_response = self._session.get(
                        f"https://sources.debian.org{raw_url}",
                        timeout=self.TIMEOUT
                    )
                    if raw_response.status_code == 200:
                        content = raw_response.text
            
            if content:
                license_name = self._parse_license_from_copyright(content)
                copyright_url = f"https://sources.debian.org/src/{package_name}/{pkg_info.version}/debian/copyright/"
                
                return LicenseInfo(
                    name=license_name or "See Copyright File",
                    url=copyright_url,
                    content=content[:2000] if content else "",
                    remark=""
                )
            
        except requests.RequestException:
            pass
        except (ValueError, KeyError):
            pass
        
        return None
    
    def _parse_license_from_copyright(self, content: str) -> Optional[str]:
        """
        Parse license name from debian/copyright file content (DEP-5 format).
        
        Returns all unique licenses found, separated by newlines for display
        in a format similar to the "安裝來源" column.
        """
        if not content:
            return None
        
        license_pattern = re.compile(r'^License:\s*(.+)$', re.MULTILINE | re.IGNORECASE)
        matches = license_pattern.findall(content)
        
        if matches:
            licenses = []
            for lic in matches:
                lic = lic.strip()
                if lic and len(lic) < 50 and not lic.startswith('.'):
                    lic_lower = lic.lower().replace(' ', '-').replace('_', '-')
                    normalized = self.LICENSE_MAPPINGS.get(lic_lower, lic)
                    if normalized not in licenses:
                        licenses.append(normalized)
            
            if len(licenses) == 0:
                return None
            elif len(licenses) == 1:
                return licenses[0]
            else:
                # Return all licenses separated by newlines
                return "\n".join(licenses)
        
        # Fallback: detect common license patterns
        content_lower = content.lower()
        
        license_checks = [
            ("Apache-2.0", ["apache license", "apache-2.0", "apache 2.0"]),
            ("MIT", ["mit license", "permission is hereby granted, free of charge"]),
            ("GPL-3.0", ["gpl-3", "gplv3", "gnu general public license.*version 3"]),
            ("GPL-2.0", ["gpl-2", "gplv2", "gnu general public license.*version 2"]),
            ("BSD-3-Clause", ["bsd-3-clause", "3-clause bsd"]),
            ("BSD-2-Clause", ["bsd-2-clause", "2-clause bsd"]),
            ("LGPL-2.1", ["lgpl-2.1", "lgplv2.1"]),
            ("PostgreSQL", ["postgresql license"]),
            ("ISC", ["isc license"]),
            ("Public Domain", ["public domain"]),
        ]
        
        for license_name, patterns in license_checks:
            for pattern in patterns:
                if re.search(pattern, content_lower):
                    return license_name
        
        return None
    
    def get_source_package_cache(self) -> dict[str, str]:
        """Get the current binary→source mapping cache."""
        return self._source_package_cache.copy()
    
    def get_vcs_cache(self) -> dict[str, dict]:
        """Get the current VCS info cache."""
        return self._vcs_cache.copy()
    
    def close(self):
        """Close the HTTP session."""
        self._session.close()
