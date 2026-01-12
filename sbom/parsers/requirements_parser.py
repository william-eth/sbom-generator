"""
Parser for Python requirements.txt files.
Supports standard pip requirements format.
"""

import re
from pathlib import Path

from .base_parser import BaseParser
from ..models import Package, PackageType


class RequirementsParser(BaseParser):
    """Parser for requirements.txt files."""
    
    # Regex pattern for parsing package specifications
    # Matches: package_name, package-name, package[extra], package[extra1,extra2]
    # With optional version specifiers: ==, >=, <=, >, <, ~=, !=, ===
    PACKAGE_PATTERN = re.compile(
        r'^'
        r'(?P<name>[a-zA-Z0-9][-a-zA-Z0-9._]*)'  # Package name
        r'(?:\[(?P<extras>[^\]]+)\])?'            # Optional extras [extra1,extra2]
        r'(?P<version_spec>(?:[<>=!~]+[^;#\s,]+(?:\s*,\s*[<>=!~]+[^;#\s,]+)*)?)'  # Version specifiers
        r'(?:\s*;\s*(?P<markers>[^#]+))?'        # Optional environment markers
        r'(?:\s*#.*)?'                            # Optional comment
        r'$'
    )
    
    # Lines to skip (special pip options)
    SKIP_PREFIXES = (
        '-r', '--requirement',
        '-c', '--constraint',
        '-e', '--editable',
        '-i', '--index-url',
        '--extra-index-url',
        '-f', '--find-links',
        '--no-index',
        '--trusted-host',
        '--pre',
        '--no-binary',
        '--only-binary',
        '--prefer-binary',
        '--require-hashes',
        '--hash',
    )
    
    @property
    def package_type(self) -> PackageType:
        return PackageType.PYPI
    
    @property
    def supported_filenames(self) -> list[str]:
        return ["requirements.txt"]
    
    def parse(self, file_path: str | Path) -> list[Package]:
        """
        Parse requirements.txt file and extract all packages.
        
        requirements.txt format examples:
        ```
        requests==2.28.0
        requests>=2.28.0,<3.0.0
        requests~=2.28.0
        requests[security]>=2.28.0
        package>=1.0.0; python_version >= "3.8"
        package==1.0.0  # comment
        ```
        
        Args:
            file_path: Path to the requirements.txt file.
            
        Returns:
            List of Package objects. All packages are marked as direct dependencies
            since requirements.txt does not distinguish between direct and transitive deps.
        """
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")
        
        packages: dict[str, Package] = {}
        
        for line in content.split("\n"):
            # Strip whitespace
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            
            # Skip special pip options
            if self._should_skip_line(line):
                continue
            
            # Parse package specification
            package_info = self._parse_package_line(line)
            if package_info:
                name, version = package_info
                # Normalize package name (PEP 503: lowercase, replace _ and . with -)
                normalized_name = self._normalize_package_name(name)
                
                if normalized_name not in packages:
                    packages[normalized_name] = Package(
                        name=name,  # Keep original name for display
                        version=version,
                        package_type=PackageType.PYPI,
                        dependencies=[],  # requirements.txt doesn't list transitive deps
                        is_direct_dependency=True  # All packages in requirements.txt are direct deps
                    )
        
        return list(packages.values())
    
    def _should_skip_line(self, line: str) -> bool:
        """Check if line should be skipped (special pip option)."""
        line_lower = line.lower()
        for prefix in self.SKIP_PREFIXES:
            if line_lower.startswith(prefix):
                return True
        return False
    
    def _parse_package_line(self, line: str) -> tuple[str, str] | None:
        """
        Parse a single package specification line.
        
        Args:
            line: A line from requirements.txt
            
        Returns:
            Tuple of (package_name, version_spec) or None if parsing fails.
        """
        # Remove inline comments first (but be careful with URLs)
        if " #" in line:
            line = line.split(" #")[0].strip()
        elif "\t#" in line:
            line = line.split("\t#")[0].strip()
        
        # Try regex match
        match = self.PACKAGE_PATTERN.match(line)
        if match:
            name = match.group("name")
            version_spec = match.group("version_spec") or ""
            
            # Extract version number from version spec
            version = self._extract_version(version_spec)
            
            return (name, version)
        
        # Fallback: simple split on version specifiers
        for sep in ("===", "==", "~=", "!=", ">=", "<=", ">", "<"):
            if sep in line:
                parts = line.split(sep, 1)
                name = parts[0].strip()
                # Remove extras from name
                if "[" in name:
                    name = name.split("[")[0]
                version = parts[1].split(",")[0].split(";")[0].strip() if len(parts) > 1 else ""
                return (name, version)
        
        # No version specifier - just package name
        name = line.split(";")[0].strip()  # Remove environment markers
        if "[" in name:
            name = name.split("[")[0]
        if name and name[0].isalpha():
            return (name, "")
        
        return None
    
    def _extract_version(self, version_spec: str) -> str:
        """
        Extract the primary version number from version specifiers.
        
        Examples:
            "==2.28.0" -> "2.28.0"
            ">=2.28.0,<3.0.0" -> "2.28.0"
            "~=2.28.0" -> "2.28.0"
            "" -> ""
        """
        if not version_spec:
            return ""
        
        # Remove leading operators and get first version
        version = re.sub(r'^[<>=!~]+', '', version_spec)
        # Take first version if multiple specified
        version = version.split(",")[0].strip()
        # Remove any remaining operators
        version = re.sub(r'^[<>=!~]+', '', version)
        
        return version
    
    def _normalize_package_name(self, name: str) -> str:
        """
        Normalize package name according to PEP 503.
        
        - Convert to lowercase
        - Replace underscores and dots with hyphens
        """
        return re.sub(r'[-_.]+', '-', name.lower())
    
    def get_direct_dependencies(self, file_path: str | Path) -> set[str]:
        """
        Get direct dependencies from requirements.txt.
        
        In requirements.txt, all listed packages are considered direct dependencies
        since the file format doesn't distinguish between direct and transitive deps.
        
        Args:
            file_path: Path to the requirements.txt file.
            
        Returns:
            Set of package names (all packages in the file).
        """
        packages = self.parse(file_path)
        return {pkg.name for pkg in packages}
