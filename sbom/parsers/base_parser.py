"""
Base parser class for lock file parsing.
Provides extensibility for future package manager support.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import Package, PackageType


class BaseParser(ABC):
    """Abstract base class for lock file parsers."""
    
    @property
    @abstractmethod
    def package_type(self) -> PackageType:
        """Return the package type this parser handles."""
        pass
    
    @property
    @abstractmethod
    def supported_filenames(self) -> list[str]:
        """Return list of supported lock file names."""
        pass
    
    def can_parse(self, file_path: str | Path) -> bool:
        """Check if this parser can handle the given file."""
        path = Path(file_path)
        return path.name in self.supported_filenames
    
    @abstractmethod
    def parse(self, file_path: str | Path) -> list[Package]:
        """
        Parse the lock file and return a list of packages.
        
        Args:
            file_path: Path to the lock file.
            
        Returns:
            List of Package objects with dependencies populated.
        """
        pass
    
    @abstractmethod
    def get_direct_dependencies(self, file_path: str | Path) -> set[str]:
        """
        Get the set of direct dependencies (top-level packages).
        
        Args:
            file_path: Path to the lock file or related manifest file.
            
        Returns:
            Set of package names that are direct dependencies.
        """
        pass

