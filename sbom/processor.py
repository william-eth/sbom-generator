"""
Package processor for unified SBOM entry generation.
Handles different package types with appropriate fetching strategies.
"""

from typing import Optional

from .cache import Cache
from .fetchers import (
    AlpineFetcher,
    DebianFetcher,
    GitHubFetcher,
    RegistryFetcher,
)
from .license import LicenseDetector
from .models import (
    LicenseInfo,
    Package,
    PackageType,
    ProcessingError,
    SBOMCategory,
    SBOMEntry,
)


class PackageProcessor:
    """
    Unified processor for generating SBOM entries from packages.
    
    Automatically selects the appropriate fetching strategy based on
    package type and SBOM category.
    """
    
    def __init__(
        self,
        github_token: Optional[str] = None,
        similarity_threshold: float = 0.9,
        cache: Optional[Cache] = None
    ):
        """
        Initialize the package processor.
        
        Args:
            github_token: GitHub Personal Access Token for API access.
            similarity_threshold: Threshold for license similarity validation.
            cache: Optional cache instance for storing fetched data.
        """
        # Application-level fetchers (npm, rubygems)
        self._registry_fetcher = RegistryFetcher()
        self._github_fetcher = GitHubFetcher(token=github_token)
        self._license_detector = LicenseDetector(similarity_threshold=similarity_threshold)
        
        # OS-level fetchers (apt, apk) - pass cache for persistent caching
        self._debian_fetcher = DebianFetcher(cache=cache)
        self._alpine_fetcher = AlpineFetcher()
        
        self._cache = cache
    
    @property
    def github_rate_limit_remaining(self) -> Optional[int]:
        """Get remaining GitHub API rate limit."""
        return self._github_fetcher.rate_limit_remaining
    
    def check_github_rate_limit(self) -> dict:
        """Check GitHub API rate limit status."""
        return self._github_fetcher.check_rate_limit()
    
    def process(
        self,
        package: Package,
        reverse_deps: dict[str, list[str]]
    ) -> tuple[SBOMEntry, Optional[ProcessingError], bool]:
        """
        Process a package and generate an SBOM entry.
        
        Args:
            package: The package to process.
            reverse_deps: Reverse dependency graph for referenced_by field.
            
        Returns:
            Tuple of (SBOMEntry, Optional[ProcessingError], cache_hit).
        """
        category = package.package_type.category
        
        if category == SBOMCategory.APPLICATION:
            return self._process_application_package(package, reverse_deps)
        else:
            return self._process_system_package(package, reverse_deps)
    
    def _format_referenced_by(
        self,
        package: Package,
        reverse_deps: dict[str, list[str]]
    ) -> str:
        """Format the 'referenced by' field for a package."""
        refs = []
        
        if package.is_direct_dependency:
            refs.append("[直接依賴]")
        
        referencing_packages = reverse_deps.get(package.name, [])
        refs.extend(sorted(referencing_packages))
        
        return ", ".join(refs)
    
    def _process_application_package(
        self,
        package: Package,
        reverse_deps: dict[str, list[str]]
    ) -> tuple[SBOMEntry, Optional[ProcessingError], bool]:
        """Process application-level packages (npm, rubygems)."""
        referenced_by = self._format_referenced_by(package, reverse_deps)
        
        repo_url = ""
        license_name = ""
        license_url = ""
        remark = ""
        error: Optional[ProcessingError] = None
        cache_hit = False
        
        package_type_str = package.package_type.value
        
        try:
            # Try cache first
            repo_info = None
            if self._cache:
                repo_info = self._cache.get_repo_info(package.name, package_type_str)
                if repo_info:
                    cache_hit = True
            
            # Fetch from registry if not cached
            if not repo_info:
                repo_info = self._registry_fetcher.get_repo_info(
                    package.name,
                    package.package_type
                )
                if self._cache:
                    self._cache.set_repo_info(package.name, package_type_str, repo_info)
            
            repo_url = repo_info.url
            
            if not repo_info.url:
                remark = "Repository URL not found"
            elif not repo_info.is_github:
                remark = "非 GitHub 來源"
                license_name = "未知"
            else:
                # Get license info from GitHub
                license_info = None
                if self._cache:
                    license_info = self._cache.get_license_info(repo_info.owner, repo_info.repo)
                    if license_info:
                        cache_hit = True
                
                if not license_info:
                    try:
                        license_info = self._github_fetcher.get_license_info(repo_info)
                        if self._cache:
                            self._cache.set_license_info(
                                repo_info.owner,
                                repo_info.repo,
                                license_info
                            )
                    except ValueError as e:
                        remark = f"無法取得 License: {str(e)}"
                        error = ProcessingError(package.name, str(e))
                        license_info = None
                
                if license_info:
                    license_name = license_info.name
                    license_url = license_info.url
                    
                    # Validate license content
                    is_standard, validation_remark = self._license_detector.validate(license_info)
                    if not is_standard:
                        license_name = f"非標準 ({license_info.spdx_id})"
                        remark = validation_remark
                    elif license_info.remark:
                        remark = license_info.remark
                        
        except ValueError as e:
            remark = "無法取得"
            error = ProcessingError(package.name, str(e))
        
        entry = SBOMEntry(
            package_name=package.name,
            referenced_by=referenced_by,
            repo_url=repo_url,
            license_name=license_name,
            license_url=license_url,
            remark=remark,
        )
        
        return entry, error, cache_hit
    
    def _process_system_package(
        self,
        package: Package,
        reverse_deps: dict[str, list[str]]
    ) -> tuple[SBOMEntry, Optional[ProcessingError], bool]:
        """Process OS-level system packages (apt, apk)."""
        referenced_by = self._format_referenced_by(package, reverse_deps)
        
        package_url = ""
        license_name = ""
        license_url = ""
        vcs_url = ""
        remark = ""
        error: Optional[ProcessingError] = None
        cache_hit = False
        
        package_type_str = package.package_type.value
        
        try:
            # Select appropriate fetcher
            if package.package_type == PackageType.APT:
                fetcher = self._debian_fetcher
            elif package.package_type == PackageType.APK:
                fetcher = self._alpine_fetcher
            else:
                raise ValueError(f"Unsupported system package type: {package.package_type}")
            
            # Try cache first
            cached_info = None
            if self._cache:
                cached_info = self._cache.get_repo_info(package.name, package_type_str)
                if cached_info:
                    cache_hit = True
                    package_url = cached_info.url
            
            # Fetch package URL
            if not package_url:
                package_url = fetcher.get_package_url(package.name, package.package_type)
            
            # Get license info (check cache with a special key)
            license_info = None
            cache_key = f"{package_type_str}_license:{package.name}"
            
            if self._cache:
                # Use a custom cache key for system package licenses
                license_info = self._cache.get_license_info(package_type_str, package.name)
                if license_info:
                    cache_hit = True
            
            if not license_info:
                license_info = fetcher.get_license_info(package.name, package.package_type)
                
                # Cache the result
                if self._cache and license_info:
                    self._cache.set_license_info(package_type_str, package.name, license_info)
            
            if license_info:
                license_name = license_info.name
                license_url = license_info.url
                # Extract VCS URL from remark if present
                if license_info.remark:
                    if license_info.remark.startswith("VCS:"):
                        vcs_url = license_info.remark.replace("VCS:", "").strip()
                    else:
                        remark = license_info.remark
                    
        except ValueError as e:
            remark = f"無法取得: {str(e)}"
            error = ProcessingError(package.name, str(e))
        except Exception as e:
            remark = f"處理錯誤: {str(e)}"
            error = ProcessingError(package.name, str(e))
        
        entry = SBOMEntry(
            package_name=package.name,
            referenced_by=referenced_by,
            repo_url=package_url,
            license_name=license_name,
            license_url=license_url,
            remark=remark,
            vcs_url=vcs_url,
        )
        
        return entry, error, cache_hit
    
    def close(self):
        """Close all fetchers and release resources."""
        self._registry_fetcher.close()
        self._github_fetcher.close()
        self._debian_fetcher.close()
        self._alpine_fetcher.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
