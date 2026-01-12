#!/usr/bin/env python3
"""
SBOM (Software Bill of Materials) Generator

A tool to generate SBOM reports from lock files and Dockerfiles.
Supports:
  - Application-level packages: yarn.lock, Gemfile.lock, requirements.txt
  - OS-level packages: Dockerfile (apt, apk)

Usage:
    python main.py                           # Process all files in input_file/
    python main.py <lock_file_path>          # Process specific file
    python main.py input_file/yarn.lock      # Process file from input folder
    python main.py input_file/requirements.txt  # Process Python requirements
    python main.py --cache                   # Use cached data
    python main.py --no-cache                # Ignore cache
    python main.py --clear-cache             # Clear cache and exit

Output:
    CSV files saved to output_file/ directory:
    - *_sbom_app_*.csv  : Application-level packages (npm, rubygems, pypi)
    - *_sbom_os_*.csv   : OS-level packages (apt, apk)
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import yaml
from tqdm import tqdm

# Default directories
SCRIPT_DIR = Path(__file__).parent.resolve()
DEFAULT_INPUT_DIR = SCRIPT_DIR / "input_file"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "output_file"

from sbom.cache import Cache
from sbom.models import (
    Package,
    PackageType,
    ProcessingError,
    SBOMCategory,
    SBOMEntry,
)
from sbom.output import CSVWriter
from sbom.parsers import GemfileParser, YarnParser, DockerfileParser, RequirementsParser
from sbom.processor import PackageProcessor


def load_config(config_path: str = "config.yaml") -> dict:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to configuration file.
        
    Returns:
        Configuration dictionary.
    """
    path = Path(config_path)
    
    if not path.exists():
        return {}
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            return config if config else {}
    except yaml.YAMLError:
        print(f"Warning: Failed to parse config file: {config_path}")
        return {}


def get_parser(file_path: Path):
    """
    Get appropriate parser for the given file.
    
    Args:
        file_path: Path to the file.
        
    Returns:
        Parser instance.
        
    Raises:
        ValueError: If file type is not supported.
    """
    yarn_parser = YarnParser()
    gemfile_parser = GemfileParser()
    dockerfile_parser = DockerfileParser()
    requirements_parser = RequirementsParser()
    
    if yarn_parser.can_parse(file_path):
        return yarn_parser
    elif gemfile_parser.can_parse(file_path):
        return gemfile_parser
    elif requirements_parser.can_parse(file_path):
        return requirements_parser
    elif dockerfile_parser.can_parse(file_path):
        return dockerfile_parser
    else:
        raise ValueError(
            f"Unsupported file type: {file_path.name}\n"
            "Supported files: yarn.lock, Gemfile.lock, requirements.txt, Dockerfile"
        )


def build_reverse_dependency_graph(packages: list[Package]) -> dict[str, list[str]]:
    """
    Build a reverse dependency graph.
    
    For each package, find which packages depend on it.
    
    Args:
        packages: List of Package objects.
        
    Returns:
        Dictionary mapping package name to list of packages that depend on it.
    """
    graph: dict[str, list[str]] = defaultdict(list)
    
    for package in packages:
        for dep in package.dependencies:
            if package.name not in graph[dep]:
                graph[dep].append(package.name)
    
    return dict(graph)


def group_packages_by_category(packages: list[Package]) -> dict[SBOMCategory, list[Package]]:
    """
    Group packages by their SBOM category.
    
    Args:
        packages: List of Package objects.
        
    Returns:
        Dictionary mapping SBOMCategory to list of packages.
    """
    grouped: dict[SBOMCategory, list[Package]] = {
        SBOMCategory.APPLICATION: [],
        SBOMCategory.OS_SYSTEM: [],
    }
    
    for package in packages:
        category = package.package_type.category
        grouped[category].append(package)
    
    return grouped


def find_input_files(input_dir: Path) -> list[Path]:
    """
    Find all supported input files in the directory.
    
    Args:
        input_dir: Directory to search.
        
    Returns:
        List of paths to supported files.
    """
    supported_files = ["yarn.lock", "Gemfile.lock", "requirements.txt"]
    input_files = []
    
    if input_dir.exists():
        # Look for lock files and requirements files
        for filename in supported_files:
            file_path = input_dir / filename
            if file_path.exists():
                input_files.append(file_path)
        
        # Look for Dockerfile and Dockerfile_* files
        for file_path in input_dir.iterdir():
            name = file_path.name.lower()
            if name == "dockerfile" or name.startswith("dockerfile_") or name.startswith("dockerfile."):
                if file_path.is_file():
                    input_files.append(file_path)
    
    return input_files


def process_file(
    file_path: Path,
    processor: PackageProcessor,
    csv_writer: CSVWriter,
    cache: Cache
) -> tuple[list[Path], int, list[ProcessingError], int]:
    """
    Process a single input file and generate SBOM report(s).
    
    Args:
        file_path: Path to the input file.
        processor: PackageProcessor instance.
        csv_writer: CSVWriter instance.
        cache: Cache instance.
        
    Returns:
        Tuple of (output_paths, total_packages, errors, cache_hits).
    """
    output_paths = []
    total_packages = 0
    all_errors: list[ProcessingError] = []
    total_cache_hits = 0
    
    # Get appropriate parser
    try:
        file_parser = get_parser(file_path)
        print(f"📦 Parsing {file_path.name}...")
    except ValueError as e:
        print(f"Error: {e}")
        return output_paths, total_packages, all_errors, total_cache_hits
    
    # Check for Dockerfile OS type support
    if isinstance(file_parser, DockerfileParser):
        dockerfile_info = file_parser.get_dockerfile_info(file_path)
        os_type = dockerfile_info.os_type
        
        # Currently only Debian-based OS is supported
        supported_os = ["debian", "ubuntu"]
        if os_type not in supported_os:
            print(f"   ❌ Error: OS type '{os_type}' is not supported yet.")
            print(f"      Currently supported: {', '.join(supported_os)}")
            print(f"      Alpine (apk) and other OS support is planned for future releases.")
            error = ProcessingError(
                package_name=file_path.name,
                reason=f"Unsupported OS: '{os_type}'. Currently only Debian-based OS (apt) is supported."
            )
            all_errors.append(error)
            return output_paths, total_packages, all_errors, total_cache_hits
        
        # Filter out APK packages if any were detected (only process APT)
        packages = [p for p in file_parser.parse(file_path) if p.package_type == PackageType.APT]
        if not packages:
            print(f"   ⚠️ No APT packages found in {file_path.name}")
            return output_paths, total_packages, all_errors, total_cache_hits
        print(f"   Found {len(packages)} packages (Debian/Ubuntu)")
    else:
        # Parse file normally for non-Dockerfile files
        packages = file_parser.parse(file_path)
        print(f"   Found {len(packages)} packages")
    
    # Group packages by category
    grouped = group_packages_by_category(packages)
    
    # Build reverse dependency graph (for all packages)
    reverse_deps = build_reverse_dependency_graph(packages)
    
    # Process each category separately
    for category, category_packages in grouped.items():
        if not category_packages:
            continue
        
        category_name = "Application" if category == SBOMCategory.APPLICATION else "OS System"
        print(f"\n🔍 Processing {category_name} packages ({len(category_packages)})...")
        
        entries: list[SBOMEntry] = []
        errors: list[ProcessingError] = []
        cache_hits = 0
        
        for package in tqdm(category_packages, desc=f"  {category_name}", unit="pkg"):
            entry, error, hit = processor.process(package, reverse_deps)
            entries.append(entry)
            if error:
                errors.append(error)
            if hit:
                cache_hits += 1
        
        # Write CSV output
        prefix = file_path.stem.replace(".", "_")
        output_path = csv_writer.write(entries, filename_prefix=prefix, category=category)
        
        print(f"   ✅ Generated: {output_path.name}")
        print(f"      Packages: {len(entries)}")
        if cache.enabled and cache_hits > 0:
            print(f"      Cache hits: {cache_hits} ({cache_hits * 100 // len(entries)}%)")
        
        output_paths.append(output_path)
        total_packages += len(entries)
        all_errors.extend(errors)
        total_cache_hits += cache_hits
    
    return output_paths, total_packages, all_errors, total_cache_hits


def main():
    """Main entry point."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Generate SBOM report from lock files and Dockerfiles.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Directories:
    Input:  {DEFAULT_INPUT_DIR}
    Output: {DEFAULT_OUTPUT_DIR}

Output File Types:
    *_sbom_app_*.csv  : Application-level packages (npm, rubygems, pypi)
    *_sbom_os_*.csv   : OS-level packages (apt, apk)

Examples:
    python main.py                              # Process all files in input_file/
    python main.py input_file/yarn.lock         # Process specific file
    python main.py input_file/requirements.txt  # Process Python requirements
    python main.py input_file/Dockerfile        # Process Dockerfile
    python main.py --cache                      # Use cached data (default)
    python main.py --no-cache                   # Ignore cache, fetch fresh data
    python main.py --clear-cache                # Clear cache and exit
        """
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default=None,
        help="Path to input file (yarn.lock, Gemfile.lock, requirements.txt, or Dockerfile). If not provided, processes all files in input_file/"
    )
    parser.add_argument(
        "--output", "-o",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Output directory for CSV files (default: {DEFAULT_OUTPUT_DIR})"
    )
    parser.add_argument(
        "--config", "-c",
        default=str(SCRIPT_DIR / "config.yaml"),
        help="Path to configuration file (default: config.yaml)"
    )
    
    # Cache options
    cache_group = parser.add_mutually_exclusive_group()
    cache_group.add_argument(
        "--cache",
        action="store_true",
        default=True,
        help="Use cached data when available (default)"
    )
    cache_group.add_argument(
        "--no-cache",
        action="store_true",
        help="Ignore cache and fetch fresh data from APIs"
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear the cache and exit"
    )
    
    args = parser.parse_args()
    
    # Initialize cache
    cache = Cache(enabled=not args.no_cache)
    
    # Handle --clear-cache
    if args.clear_cache:
        cache.clear()
        print("✅ Cache cleared successfully.")
        sys.exit(0)
    
    # Determine input files to process
    if args.input_file:
        input_file_path = Path(args.input_file)
        if not input_file_path.exists():
            print(f"Error: File not found: {args.input_file}")
            sys.exit(1)
        input_files = [input_file_path]
    else:
        # Find input files in input directory
        input_files = find_input_files(DEFAULT_INPUT_DIR)
        if not input_files:
            print(f"Error: No supported files found in {DEFAULT_INPUT_DIR}")
            print("Please place yarn.lock, Gemfile.lock, requirements.txt, or Dockerfile in the input_file/ directory")
            sys.exit(1)
        print(f"📂 Found {len(input_files)} file(s) in {DEFAULT_INPUT_DIR}")
        for f in input_files:
            print(f"   - {f.name}")
        print()
    
    # Ensure output directory exists
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load configuration
    config = load_config(args.config)
    github_token = config.get("GITHUB_TOKEN", "")
    similarity_threshold = config.get("LICENSE_SIMILARITY_THRESHOLD", 0.9)
    
    # Show token status
    if github_token:
        print("✓ GitHub token configured (5000 requests/hour)")
    else:
        print("⚠ No GitHub token configured (60 requests/hour)")
        print("  Set GITHUB_TOKEN in config.yaml for higher rate limit")
    
    # Show cache status
    if cache.enabled:
        stats = cache.get_stats()
        print(f"✓ Cache enabled ({stats['valid_entries']} cached entries)")
    else:
        print("⚠ Cache disabled (--no-cache)")
    print()
    
    # Initialize processor
    processor = PackageProcessor(
        github_token=github_token if github_token else None,
        similarity_threshold=similarity_threshold,
        cache=cache
    )
    
    # Check initial GitHub rate limit
    if github_token:
        rate_info = processor.check_github_rate_limit()
        print(f"📊 GitHub API rate limit: {rate_info['remaining']}/{rate_info['limit']}")
        print()
    
    # Initialize CSV writer
    csv_writer = CSVWriter(output_dir=output_dir)
    
    # Process each input file
    all_output_paths = []
    total_packages = 0
    all_errors: list[ProcessingError] = []
    total_cache_hits = 0
    
    with processor, cache:
        for input_file_path in input_files:
            paths, pkgs, errors, hits = process_file(
                input_file_path,
                processor,
                csv_writer,
                cache
            )
            all_output_paths.extend(paths)
            total_packages += pkgs
            all_errors.extend(errors)
            total_cache_hits += hits
            
            if len(input_files) > 1:
                print()
                print("-" * 60)
    
    # Report errors
    if all_errors:
        print()
        print(f"⚠️  無法取得資訊的套件 ({len(all_errors)} 個):")
        print("-" * 50)
        for err in all_errors[:10]:  # Show first 10 errors
            print(f"  • {err.package_name}: {err.reason}")
        if len(all_errors) > 10:
            print(f"  ... and {len(all_errors) - 10} more")
    
    # Summary
    print()
    print("=" * 60)
    print(f"📋 Summary: Generated {len(all_output_paths)} SBOM report(s)")
    print(f"   Total packages processed: {total_packages}")
    if cache.enabled and total_cache_hits > 0:
        print(f"   Total cache hits: {total_cache_hits}")
    
    # Group output files by category
    app_files = [p for p in all_output_paths if "_app_" in p.name]
    os_files = [p for p in all_output_paths if "_os_" in p.name]
    
    if app_files:
        print(f"\n   📦 Application-level SBOM:")
        for path in app_files:
            print(f"      - {path.name}")
    
    if os_files:
        print(f"\n   🐧 OS-level SBOM:")
        for path in os_files:
            print(f"      - {path.name}")
    
    # Check remaining GitHub rate limit
    if github_token and processor.github_rate_limit_remaining is not None:
        print()
        print(f"📊 Remaining GitHub API calls: {processor.github_rate_limit_remaining}")
    
    # Show cache stats
    if cache.enabled:
        stats = cache.get_stats()
        print(f"📦 Cache entries: {stats['total_entries']}")


if __name__ == "__main__":
    main()
