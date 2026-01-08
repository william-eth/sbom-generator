"""
Parser for Dockerfile files.
Extracts base image information and installed system packages.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from .base_parser import BaseParser
from ..models import Package, PackageType


@dataclass
class DockerfileInfo:
    """Information extracted from a Dockerfile."""
    base_images: list[dict] = field(default_factory=list)  # List of FROM images
    apt_packages: list[str] = field(default_factory=list)  # Debian/Ubuntu packages
    apk_packages: list[str] = field(default_factory=list)  # Alpine packages
    os_type: str = ""  # Detected OS type: debian, ubuntu, alpine, etc.


class DockerfileParser(BaseParser):
    """Parser for Dockerfile files."""
    
    # Common base image patterns to detect OS type
    OS_PATTERNS = {
        "alpine": re.compile(r"alpine", re.IGNORECASE),
        "debian": re.compile(r"(debian|trixie|bookworm|bullseye|buster|stretch)", re.IGNORECASE),
        "ubuntu": re.compile(r"(ubuntu|jammy|focal|bionic|noble)", re.IGNORECASE),
        "centos": re.compile(r"centos", re.IGNORECASE),
        "rhel": re.compile(r"(rhel|redhat)", re.IGNORECASE),
        "fedora": re.compile(r"fedora", re.IGNORECASE),
    }
    
    @property
    def package_type(self) -> PackageType:
        # Will be determined dynamically based on OS type
        return PackageType.APT
    
    @property
    def supported_filenames(self) -> list[str]:
        return ["Dockerfile", "Dockerfile_1", "dockerfile"]
    
    def can_parse(self, file_path: str | Path) -> bool:
        """Check if this parser can handle the given file."""
        path = Path(file_path)
        # Match Dockerfile or Dockerfile.* or Dockerfile_*
        name = path.name.lower()
        return name == "dockerfile" or name.startswith("dockerfile.") or name.startswith("dockerfile_")
    
    def parse(self, file_path: str | Path) -> list[Package]:
        """
        Parse Dockerfile and extract installed packages.
        
        Returns:
            List of Package objects representing system packages.
        """
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")
        
        # Parse Dockerfile structure
        dockerfile_info = self._parse_dockerfile(content)
        
        packages: list[Package] = []
        
        # Create Package objects for APT packages
        for pkg_name in dockerfile_info.apt_packages:
            packages.append(Package(
                name=pkg_name,
                version="",  # Version usually not specified in Dockerfile
                package_type=PackageType.APT,
                dependencies=[],
                is_direct_dependency=True  # All are direct dependencies in Dockerfile
            ))
        
        # Create Package objects for APK packages
        for pkg_name in dockerfile_info.apk_packages:
            packages.append(Package(
                name=pkg_name,
                version="",
                package_type=PackageType.APK,
                dependencies=[],
                is_direct_dependency=True
            ))
        
        return packages
    
    def get_direct_dependencies(self, file_path: str | Path) -> set[str]:
        """All packages in Dockerfile are considered direct dependencies."""
        packages = self.parse(file_path)
        return {pkg.name for pkg in packages}
    
    def get_dockerfile_info(self, file_path: str | Path) -> DockerfileInfo:
        """Get detailed Dockerfile information including base images and OS type."""
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")
        return self._parse_dockerfile(content)
    
    def _parse_dockerfile(self, content: str) -> DockerfileInfo:
        """Parse Dockerfile content and extract all relevant information."""
        info = DockerfileInfo()
        
        # Join continuation lines (lines ending with \) FIRST
        # This is critical for multi-line ENV values like FONTS_CORE="\n    fonts-dejavu ..."
        normalized_content = self._normalize_continuation_lines(content)
        
        # Extract ARG values for variable substitution (from normalized content)
        args = self._extract_args(normalized_content)
        
        # Extract ENV values (from normalized content to handle multi-line values)
        envs = self._extract_envs(normalized_content)
        
        # Resolve ENV variables that reference other ENV variables (e.g., RUNNING_FONTS="$FONTS_CORE $FONTS_CHINESE")
        envs = self._resolve_env_references(envs, args)
        
        # Combine ARG and ENV for variable substitution
        variables = {**args, **envs}
        
        # Parse FROM instructions
        info.base_images = self._parse_from_instructions(normalized_content, variables)
        
        # Detect OS type from base images
        info.os_type = self._detect_os_type(info.base_images)
        
        # Parse RUN instructions for package installations
        apt_packages, apk_packages = self._parse_run_instructions(normalized_content, variables)
        info.apt_packages = apt_packages
        info.apk_packages = apk_packages
        
        return info
    
    def _normalize_continuation_lines(self, content: str) -> str:
        """Join lines that end with backslash."""
        lines = content.split("\n")
        normalized = []
        current_line = ""
        
        for line in lines:
            stripped = line.rstrip()
            if stripped.endswith("\\"):
                # Continuation line - append without the backslash
                current_line += stripped[:-1] + " "
            else:
                current_line += stripped
                normalized.append(current_line)
                current_line = ""
        
        if current_line:
            normalized.append(current_line)
        
        return "\n".join(normalized)
    
    def _extract_args(self, content: str) -> dict[str, str]:
        """Extract ARG declarations from Dockerfile."""
        args = {}
        # Match: ARG NAME or ARG NAME=value
        pattern = re.compile(r"^\s*ARG\s+([A-Za-z_][A-Za-z0-9_]*)(?:=(.*))?", re.MULTILINE)
        
        for match in pattern.finditer(content):
            name = match.group(1)
            value = match.group(2) or ""
            args[name] = value.strip().strip('"').strip("'")
        
        return args
    
    def _extract_envs(self, content: str) -> dict[str, str]:
        """
        Extract ENV declarations from Dockerfile.
        
        Handles multiple formats:
        - ENV NAME=value
        - ENV NAME="value with spaces"
        - ENV NAME value (space separated, legacy format)
        
        Note: This should be called on normalized content (after line continuation processing)
        to properly handle multi-line ENV values.
        """
        envs = {}
        
        # Pattern for ENV NAME="quoted value" (handles multi-line values after normalization)
        pattern_quoted = re.compile(
            r'^\s*ENV\s+([A-Za-z_][A-Za-z0-9_]*)="([^"]*)"',
            re.MULTILINE
        )
        for match in pattern_quoted.finditer(content):
            name = match.group(1)
            value = match.group(2)
            envs[name] = value
        
        # Pattern for ENV NAME='single quoted value'
        pattern_single_quoted = re.compile(
            r"^\s*ENV\s+([A-Za-z_][A-Za-z0-9_]*)='([^']*)'",
            re.MULTILINE
        )
        for match in pattern_single_quoted.finditer(content):
            name = match.group(1)
            value = match.group(2)
            if name not in envs:
                envs[name] = value
        
        # Pattern for ENV NAME=unquoted_value (no spaces)
        pattern_unquoted = re.compile(
            r'^\s*ENV\s+([A-Za-z_][A-Za-z0-9_]*)=([^\s"\']+)',
            re.MULTILINE
        )
        for match in pattern_unquoted.finditer(content):
            name = match.group(1)
            value = match.group(2)
            if name not in envs:
                envs[name] = value
        
        # Pattern for ENV NAME value (space separated, legacy format)
        pattern_space = re.compile(
            r'^\s*ENV\s+([A-Za-z_][A-Za-z0-9_]*)\s+(?!=)("[^"]*"|\'[^\']*\'|\S+)',
            re.MULTILINE
        )
        for match in pattern_space.finditer(content):
            name = match.group(1)
            value = match.group(2).strip('"').strip("'")
            if name not in envs:
                envs[name] = value
        
        return envs
    
    def _resolve_env_references(self, envs: dict[str, str], args: dict[str, str]) -> dict[str, str]:
        """
        Resolve ENV variables that reference other ENV or ARG variables.
        
        For example: RUNNING_FONTS="$FONTS_CORE $FONTS_CHINESE" should be expanded
        to contain all the fonts from both variables.
        
        This performs multiple passes to handle nested references.
        """
        # Combine args and envs for lookup (args can be referenced in envs)
        all_vars = {**args, **envs}
        resolved = dict(envs)
        
        # Multiple passes to handle references to variables defined earlier
        max_passes = 10  # Prevent infinite loops
        for _ in range(max_passes):
            changed = False
            for name, value in resolved.items():
                new_value = self._substitute_variables(value, all_vars)
                if new_value != value:
                    resolved[name] = new_value
                    all_vars[name] = new_value
                    changed = True
            if not changed:
                break
        
        return resolved
    
    def _substitute_variables(self, text: str, variables: dict[str, str]) -> str:
        """Substitute $VAR and ${VAR} with their values."""
        result = text
        
        # Replace ${VAR} format
        for name, value in variables.items():
            result = result.replace(f"${{{name}}}", value)
            result = result.replace(f"${name}", value)
        
        # Handle ${VAR:-default} format
        default_pattern = re.compile(r'\$\{([A-Za-z_][A-Za-z0-9_]*):-([^}]*)\}')
        result = default_pattern.sub(
            lambda m: variables.get(m.group(1), m.group(2)),
            result
        )
        
        return result
    
    def _parse_from_instructions(self, content: str, variables: dict[str, str]) -> list[dict]:
        """Parse FROM instructions to extract base images."""
        images = []
        # Match: FROM image:tag AS stage
        pattern = re.compile(
            r"^\s*FROM\s+([^\s]+)(?:\s+AS\s+([^\s]+))?",
            re.MULTILINE | re.IGNORECASE
        )
        
        for match in pattern.finditer(content):
            image_spec = self._substitute_variables(match.group(1), variables)
            stage_name = match.group(2) or ""
            
            # Parse image:tag
            if ":" in image_spec:
                image_name, tag = image_spec.rsplit(":", 1)
            else:
                image_name = image_spec
                tag = "latest"
            
            images.append({
                "full": image_spec,
                "name": image_name,
                "tag": tag,
                "stage": stage_name
            })
        
        return images
    
    def _detect_os_type(self, base_images: list[dict]) -> str:
        """Detect OS type from base images."""
        for image in base_images:
            image_str = f"{image['name']}:{image['tag']}"
            
            for os_type, pattern in self.OS_PATTERNS.items():
                if pattern.search(image_str):
                    return os_type
        
        # Default to debian if using official images like ruby, node, python
        for image in base_images:
            name = image['name'].lower()
            # Official images without alpine tag are usually debian-based
            if any(lang in name for lang in ['ruby', 'python', 'node', 'golang', 'php']):
                tag = image['tag'].lower()
                if 'alpine' in tag:
                    return "alpine"
                elif any(d in tag for d in ['slim', 'bullseye', 'bookworm', 'buster', 'trixie']):
                    return "debian"
        
        return "unknown"
    
    def _parse_run_instructions(
        self,
        content: str,
        variables: dict[str, str]
    ) -> tuple[list[str], list[str]]:
        """Parse RUN instructions to extract package installations."""
        apt_packages: list[str] = []
        apk_packages: list[str] = []
        
        # Extract all RUN instructions
        run_pattern = re.compile(r"^\s*RUN\s+(.+)", re.MULTILINE | re.IGNORECASE)
        
        for match in run_pattern.finditer(content):
            run_command = self._substitute_variables(match.group(1), variables)
            
            # Parse apt-get install commands
            apt_packages.extend(self._parse_apt_install(run_command))
            
            # Parse apk add commands
            apk_packages.extend(self._parse_apk_add(run_command))
        
        # Remove duplicates while preserving order
        apt_packages = list(dict.fromkeys(apt_packages))
        apk_packages = list(dict.fromkeys(apk_packages))
        
        return apt_packages, apk_packages
    
    def _parse_apt_install(self, command: str) -> list[str]:
        """Parse apt-get install or apt install commands."""
        packages = []
        
        # Pattern to match apt-get install or apt install
        # Handles: apt-get install -y pkg1 pkg2
        #          apt-get install -qq -y pkg1 pkg2
        #          DEBIAN_FRONTEND=noninteractive apt-get install ...
        apt_pattern = re.compile(
            r"(?:apt-get|apt)\s+install\s+([^&|;]+)",
            re.IGNORECASE
        )
        
        for match in apt_pattern.finditer(command):
            install_args = match.group(1)
            
            # Extract package names (skip flags like -y, -qq, --no-install-recommends)
            tokens = install_args.split()
            for token in tokens:
                token = token.strip()
                # Skip empty, flags, and options
                if not token or token.startswith("-"):
                    continue
                # Skip common non-package arguments
                if token in ("&&", "||", ";", "|"):
                    break
                # Package name validation (letters, numbers, hyphens, plus, dots)
                if re.match(r'^[a-zA-Z0-9][a-zA-Z0-9+.\-]*$', token):
                    packages.append(token)
        
        return packages
    
    def _parse_apk_add(self, command: str) -> list[str]:
        """Parse apk add commands."""
        packages = []
        
        # Pattern to match apk add
        # Handles: apk add --no-cache pkg1 pkg2
        #          apk add --update pkg1
        apk_pattern = re.compile(
            r"apk\s+add\s+([^&|;]+)",
            re.IGNORECASE
        )
        
        for match in apk_pattern.finditer(command):
            add_args = match.group(1)
            
            # Extract package names (skip flags like --no-cache, --update)
            tokens = add_args.split()
            for token in tokens:
                token = token.strip()
                # Skip empty and flags
                if not token or token.startswith("-"):
                    continue
                # Skip common non-package arguments
                if token in ("&&", "||", ";", "|"):
                    break
                # Package name validation
                if re.match(r'^[a-zA-Z0-9][a-zA-Z0-9+.\-]*$', token):
                    packages.append(token)
        
        return packages
