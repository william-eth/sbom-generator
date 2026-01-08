"""
Base fetcher class for license information.
Provides extensibility for different package sources.
"""

from abc import ABC, abstractmethod
from typing import Optional

from ..models import LicenseInfo, PackageType


class BaseLicenseFetcher(ABC):
    """Abstract base class for license fetchers."""
    
    @property
    @abstractmethod
    def supported_package_types(self) -> list[PackageType]:
        """Return list of package types this fetcher supports."""
        pass
    
    def can_fetch(self, package_type: PackageType) -> bool:
        """Check if this fetcher can handle the given package type."""
        return package_type in self.supported_package_types
    
    @abstractmethod
    def get_license_info(self, package_name: str, package_type: PackageType) -> LicenseInfo:
        """
        Get license information for a package.
        
        Args:
            package_name: Name of the package.
            package_type: Type of the package.
            
        Returns:
            LicenseInfo object with license details.
        """
        pass
    
    @abstractmethod
    def get_package_url(self, package_name: str, package_type: PackageType) -> str:
        """
        Get the package URL (registry, tracker, or source).
        
        Args:
            package_name: Name of the package.
            package_type: Type of the package.
            
        Returns:
            URL string for the package.
        """
        pass
    
    def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
