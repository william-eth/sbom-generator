"""
Parser for yarn.lock files.
Supports Yarn v1 (classic) lock file format.
"""

import re
from pathlib import Path

from .base_parser import BaseParser
from ..models import Package, PackageType


class YarnParser(BaseParser):
    """Parser for yarn.lock files (Yarn v1 format)."""
    
    @property
    def package_type(self) -> PackageType:
        return PackageType.NPM
    
    @property
    def supported_filenames(self) -> list[str]:
        return ["yarn.lock"]
    
    def parse(self, file_path: str | Path) -> list[Package]:
        """
        Parse yarn.lock file and extract all packages with dependencies.
        
        yarn.lock format (v1):
        ```
        package-name@^1.0.0, package-name@~1.0.0:
          version "1.0.5"
          resolved "https://registry.yarnpkg.com/..."
          dependencies:
            dep-a "^2.0.0"
            dep-b "^3.0.0"
        ```
        """
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")
        
        # Get direct dependencies to mark them
        direct_deps = self.get_direct_dependencies(file_path)
        
        packages: dict[str, Package] = {}
        current_package_names: list[str] = []
        current_version: str = ""
        current_dependencies: list[str] = []
        in_dependencies_block = False
        in_optional_dependencies_block = False
        
        lines = content.split("\n")
        
        for line in lines:
            # Skip comments and empty lines
            if line.startswith("#") or not line.strip():
                # If we were parsing a package, save it
                if current_package_names and current_version:
                    self._save_package(
                        packages, current_package_names, current_version,
                        current_dependencies, direct_deps
                    )
                    current_package_names = []
                    current_version = ""
                    current_dependencies = []
                    in_dependencies_block = False
                    in_optional_dependencies_block = False
                continue
            
            # Check for new package entry (no leading whitespace, ends with colon)
            if not line.startswith(" ") and line.rstrip().endswith(":"):
                # Save previous package if exists
                if current_package_names and current_version:
                    self._save_package(
                        packages, current_package_names, current_version,
                        current_dependencies, direct_deps
                    )
                
                # Parse new package header
                current_package_names = self._parse_package_header(line)
                current_version = ""
                current_dependencies = []
                in_dependencies_block = False
                in_optional_dependencies_block = False
                continue
            
            # Parse package details
            stripped = line.strip()
            
            # Version line
            if stripped.startswith("version "):
                match = re.match(r'version\s+"([^"]+)"', stripped)
                if match:
                    current_version = match.group(1)
                continue
            
            # Dependencies block start
            if stripped == "dependencies:":
                in_dependencies_block = True
                in_optional_dependencies_block = False
                continue
            
            # Optional dependencies block start (we include these too)
            if stripped == "optionalDependencies:":
                in_optional_dependencies_block = True
                in_dependencies_block = False
                continue
            
            # Other blocks that end dependencies parsing
            if stripped in ("peerDependencies:", "peerDependenciesMeta:", 
                           "dependenciesMeta:", "bin:", "binDependencies:"):
                in_dependencies_block = False
                in_optional_dependencies_block = False
                continue
            
            # Parse dependency entry
            if in_dependencies_block or in_optional_dependencies_block:
                dep_match = re.match(r'"?([^"@\s]+)"?\s+"[^"]+"', stripped)
                if dep_match:
                    dep_name = dep_match.group(1)
                    if dep_name not in current_dependencies:
                        current_dependencies.append(dep_name)
        
        # Save last package
        if current_package_names and current_version:
            self._save_package(
                packages, current_package_names, current_version,
                current_dependencies, direct_deps
            )
        
        return list(packages.values())
    
    def _parse_package_header(self, line: str) -> list[str]:
        """
        Parse package header line to extract package names.
        
        Examples:
        - 'lodash@^4.17.21:'
        - '"@babel/core@^7.0.0", "@babel/core@^7.1.0":'
        - 'accepts@~1.3.7:'
        """
        # Remove trailing colon
        header = line.rstrip().rstrip(":")
        
        # Split by comma for multiple version specifiers
        parts = re.split(r',\s*', header)
        
        names = []
        for part in parts:
            part = part.strip().strip('"')
            # Extract package name (before @version)
            # Handle scoped packages like @babel/core@^7.0.0
            if part.startswith("@"):
                # Scoped package: @scope/name@version
                match = re.match(r'(@[^@/]+/[^@]+)@', part)
                if match:
                    name = match.group(1)
                    if name not in names:
                        names.append(name)
            else:
                # Regular package: name@version
                match = re.match(r'([^@]+)@', part)
                if match:
                    name = match.group(1)
                    if name not in names:
                        names.append(name)
        
        return names
    
    def _save_package(
        self,
        packages: dict[str, Package],
        names: list[str],
        version: str,
        dependencies: list[str],
        direct_deps: set[str]
    ) -> None:
        """Save package to the packages dict, avoiding duplicates."""
        for name in names:
            # Use name as key (we only keep one version per package name)
            # In a real lock file, there might be multiple versions
            # We keep the first encountered or update if it's a direct dependency
            if name not in packages:
                packages[name] = Package(
                    name=name,
                    version=version,
                    package_type=PackageType.NPM,
                    dependencies=dependencies.copy(),
                    is_direct_dependency=name in direct_deps
                )
            elif name in direct_deps:
                # Update to mark as direct dependency
                packages[name].is_direct_dependency = True
    
    def get_direct_dependencies(self, file_path: str | Path) -> set[str]:
        """
        Get direct dependencies from package.json.
        
        Looks for package.json in the same directory as yarn.lock.
        """
        import json
        
        path = Path(file_path)
        package_json_path = path.parent / "package.json"
        
        direct_deps: set[str] = set()
        
        if package_json_path.exists():
            try:
                with open(package_json_path, "r", encoding="utf-8") as f:
                    package_data = json.load(f)
                
                # Collect all dependency types
                for dep_key in ("dependencies", "devDependencies", 
                               "peerDependencies", "optionalDependencies"):
                    deps = package_data.get(dep_key, {})
                    direct_deps.update(deps.keys())
            except (json.JSONDecodeError, IOError):
                pass
        
        return direct_deps

