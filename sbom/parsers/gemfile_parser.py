"""
Parser for Gemfile.lock files.
Supports Ruby Bundler lock file format.
"""

import re
from pathlib import Path

from .base_parser import BaseParser
from ..models import Package, PackageType


class GemfileParser(BaseParser):
    """Parser for Gemfile.lock files (Ruby Bundler format)."""
    
    @property
    def package_type(self) -> PackageType:
        return PackageType.RUBYGEMS
    
    @property
    def supported_filenames(self) -> list[str]:
        return ["Gemfile.lock"]
    
    def parse(self, file_path: str | Path) -> list[Package]:
        """
        Parse Gemfile.lock file and extract all packages with dependencies.
        
        Gemfile.lock format:
        ```
        GEM
          remote: https://rubygems.org/
          specs:
            actioncable (7.0.4)
              actionpack (= 7.0.4)
              activesupport (= 7.0.4)
            actionpack (7.0.4)
              actionview (= 7.0.4)
        
        DEPENDENCIES
          rails (~> 7.0.4)
          puma (~> 5.0)
        ```
        """
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")
        
        # Get direct dependencies from DEPENDENCIES section
        direct_deps = self.get_direct_dependencies(file_path)
        
        packages: dict[str, Package] = {}
        current_section = None
        current_package: Package | None = None
        
        lines = content.split("\n")
        
        for line in lines:
            stripped = line.rstrip()
            
            # Detect section headers
            if stripped in ("GEM", "GIT", "PATH", "PLUGIN SOURCE", 
                           "PLATFORMS", "DEPENDENCIES", "RUBY VERSION", 
                           "BUNDLED WITH"):
                current_section = stripped
                current_package = None
                continue
            
            # Skip non-GEM sections for package parsing
            # (GIT and PATH could be added for more complete support)
            if current_section not in ("GEM", "GIT", "PATH"):
                continue
            
            # Skip remote and specs lines
            if stripped.strip() in ("remote: https://rubygems.org/", "specs:") or \
               stripped.strip().startswith("remote:") or \
               stripped.strip() == "specs:":
                continue
            
            # Empty line resets current package
            if not stripped.strip():
                current_package = None
                continue
            
            # Count leading spaces to determine nesting level
            leading_spaces = len(line) - len(line.lstrip())
            
            # Package definition (4 spaces indent under specs:)
            # Format: "    package-name (version)"
            if leading_spaces == 4 and current_section in ("GEM", "GIT", "PATH"):
                match = re.match(r'\s{4}(\S+)\s+\(([^)]+)\)', line)
                if match:
                    name = match.group(1)
                    version = match.group(2)
                    
                    current_package = Package(
                        name=name,
                        version=version,
                        package_type=PackageType.RUBYGEMS,
                        dependencies=[],
                        is_direct_dependency=name in direct_deps
                    )
                    
                    # Only keep first version encountered
                    if name not in packages:
                        packages[name] = current_package
                    elif name in direct_deps:
                        packages[name].is_direct_dependency = True
                        current_package = packages[name]
                continue
            
            # Dependency of current package (6 spaces indent)
            # Format: "      dependency-name (>= version)"
            if leading_spaces == 6 and current_package is not None:
                match = re.match(r'\s{6}(\S+)', line)
                if match:
                    dep_name = match.group(1)
                    if dep_name not in current_package.dependencies:
                        current_package.dependencies.append(dep_name)
        
        return list(packages.values())
    
    def get_direct_dependencies(self, file_path: str | Path) -> set[str]:
        """
        Get direct dependencies from the DEPENDENCIES section of Gemfile.lock.
        
        Also tries to parse Gemfile if available for more accurate results.
        """
        path = Path(file_path)
        direct_deps: set[str] = set()
        
        # Parse DEPENDENCIES section from Gemfile.lock
        try:
            content = path.read_text(encoding="utf-8")
            in_dependencies = False
            
            for line in content.split("\n"):
                stripped = line.strip()
                
                if stripped == "DEPENDENCIES":
                    in_dependencies = True
                    continue
                
                if in_dependencies:
                    # Empty line or new section ends DEPENDENCIES
                    if not stripped or (not line.startswith(" ") and stripped):
                        if stripped in ("RUBY VERSION", "BUNDLED WITH", 
                                       "PLATFORMS", "GEM", "GIT", "PATH"):
                            break
                    
                    # Parse dependency line
                    # Format: "  gem-name" or "  gem-name (~> 1.0)"
                    if line.startswith("  ") and stripped:
                        match = re.match(r'(\S+?)(?:\s+\(|!|$)', stripped)
                        if match:
                            dep_name = match.group(1)
                            direct_deps.add(dep_name)
        except IOError:
            pass
        
        # Optionally parse Gemfile for more accurate direct dependencies
        gemfile_path = path.parent / "Gemfile"
        if gemfile_path.exists():
            try:
                gemfile_content = gemfile_path.read_text(encoding="utf-8")
                # Simple regex to find gem declarations
                # Handles: gem 'name', gem "name", gem('name'), etc.
                gem_pattern = re.compile(
                    r'^\s*gem\s*[(\s]+[\'"]([^\'"]+)[\'"]',
                    re.MULTILINE
                )
                for match in gem_pattern.finditer(gemfile_content):
                    direct_deps.add(match.group(1))
            except IOError:
                pass
        
        return direct_deps

