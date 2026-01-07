#!/usr/bin/env python3
"""
SBOM (Software Bill of Materials) Generator

A tool to generate SBOM reports from lock files (yarn.lock, Gemfile.lock).
Extracts package information, repository URLs, and license details.

Usage:
    python main.py                           # Process all files in input_file/
    python main.py <lock_file_path>          # Process specific file
    python main.py input_file/yarn.lock      # Process file from input folder
    python main.py --cache                   # Use cached data
    python main.py --no-cache                # Ignore cache
    python main.py --clear-cache             # Clear cache and exit

Output:
    CSV file saved to output_file/ directory (UTF-8 with BOM for Excel compatibility)
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

import yaml
from tqdm import tqdm

# Default directories
SCRIPT_DIR = Path(__file__).parent.resolve()
DEFAULT_INPUT_DIR = SCRIPT_DIR / "input_file"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "output_file"

from sbom.cache import Cache
from sbom.fetchers import GitHubFetcher, RegistryFetcher
from sbom.license import LicenseDetector
from sbom.models import (
    Package,
    PackageType,
    ProcessingError,
    RepoInfo,
    SBOMEntry,
)
from sbom.output import CSVWriter
from sbom.parsers import GemfileParser, YarnParser


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
    Get appropriate parser for the given lock file.
    
    Args:
        file_path: Path to the lock file.
        
    Returns:
        Parser instance.
        
    Raises:
        ValueError: If file type is not supported.
    """
    yarn_parser = YarnParser()
    gemfile_parser = GemfileParser()
    
    if yarn_parser.can_parse(file_path):
        return yarn_parser
    elif gemfile_parser.can_parse(file_path):
        return gemfile_parser
    else:
        raise ValueError(
            f"Unsupported file type: {file_path.name}\n"
            "Supported files: yarn.lock, Gemfile.lock"
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


def format_referenced_by(
    package: Package,
    reverse_deps: dict[str, list[str]]
) -> str:
    """
    Format the 'referenced by' field for a package.
    
    Args:
        package: The package.
        reverse_deps: Reverse dependency graph.
        
    Returns:
        Formatted string with referenced packages.
    """
    refs = []
    
    # Mark direct dependencies
    if package.is_direct_dependency:
        refs.append("[直接依賴]")
    
    # Add packages that reference this one
    referencing_packages = reverse_deps.get(package.name, [])
    refs.extend(sorted(referencing_packages))
    
    return ", ".join(refs)


def process_package(
    package: Package,
    registry_fetcher: RegistryFetcher,
    github_fetcher: GitHubFetcher,
    license_detector: LicenseDetector,
    reverse_deps: dict[str, list[str]],
    cache: Optional[Cache] = None
) -> tuple[SBOMEntry, Optional[ProcessingError], bool]:
    """
    Process a single package to extract SBOM information.
    
    Args:
        package: Package to process.
        registry_fetcher: Registry fetcher for repo URLs.
        github_fetcher: GitHub fetcher for license info.
        license_detector: License detector for validation.
        reverse_deps: Reverse dependency graph.
        cache: Optional cache for storing/retrieving package info.
        
    Returns:
        Tuple of (SBOMEntry, Optional[ProcessingError], cache_hit).
    """
    referenced_by = format_referenced_by(package, reverse_deps)
    
    # Default values for error cases
    repo_url = ""
    license_name = ""
    license_url = ""
    remark = ""
    error: Optional[ProcessingError] = None
    cache_hit = False
    
    package_type_str = package.package_type.value
    
    try:
        # Try to get repo info from cache first
        repo_info = None
        if cache:
            repo_info = cache.get_repo_info(package.name, package_type_str)
            if repo_info:
                cache_hit = True
        
        # If not in cache, fetch from registry
        if not repo_info:
            repo_info = registry_fetcher.get_repo_info(
                package.name,
                package.package_type
            )
            # Store in cache
            if cache:
                cache.set_repo_info(package.name, package_type_str, repo_info)
        
        repo_url = repo_info.url
        
        if not repo_info.url:
            remark = "Repository URL not found"
        elif not repo_info.is_github:
            # Non-GitHub source
            remark = "非 GitHub 來源"
            license_name = "未知"
        else:
            # Try to get license info from cache first
            license_info = None
            if cache:
                license_info = cache.get_license_info(repo_info.owner, repo_info.repo)
                if license_info:
                    cache_hit = True
            
            # If not in cache, fetch from GitHub
            if not license_info:
                try:
                    license_info = github_fetcher.get_license_info(repo_info)
                    # Store in cache
                    if cache:
                        cache.set_license_info(repo_info.owner, repo_info.repo, license_info)
                except ValueError as e:
                    remark = f"無法取得 License: {str(e)}"
                    error = ProcessingError(package.name, str(e))
                    license_info = None
            
            if license_info:
                license_name = license_info.name
                license_url = license_info.url
                
                # Validate license content
                is_standard, validation_remark = license_detector.validate(license_info)
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


def find_lock_files(input_dir: Path) -> list[Path]:
    """
    Find all supported lock files in the input directory.
    
    Args:
        input_dir: Directory to search for lock files.
        
    Returns:
        List of paths to lock files.
    """
    supported_files = ["yarn.lock", "Gemfile.lock"]
    lock_files = []
    
    if input_dir.exists():
        for filename in supported_files:
            file_path = input_dir / filename
            if file_path.exists():
                lock_files.append(file_path)
    
    return lock_files


def main():
    """Main entry point."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Generate SBOM report from lock files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Directories:
    Input:  {DEFAULT_INPUT_DIR}
    Output: {DEFAULT_OUTPUT_DIR}

Examples:
    python main.py                              # Process all files in input_file/
    python main.py input_file/yarn.lock         # Process specific file
    python main.py /path/to/Gemfile.lock        # Process file from any path
    python main.py --cache                      # Use cached data (default)
    python main.py --no-cache                   # Ignore cache, fetch fresh data
    python main.py --clear-cache                # Clear cache and exit
        """
    )
    parser.add_argument(
        "lock_file",
        nargs="?",
        default=None,
        help="Path to lock file (yarn.lock or Gemfile.lock). If not provided, processes all files in input_file/"
    )
    parser.add_argument(
        "--output", "-o",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Output directory for CSV file (default: {DEFAULT_OUTPUT_DIR})"
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
    
    # Determine lock files to process
    if args.lock_file:
        lock_file_path = Path(args.lock_file)
        if not lock_file_path.exists():
            print(f"Error: File not found: {args.lock_file}")
            sys.exit(1)
        lock_files = [lock_file_path]
    else:
        # Find lock files in input directory
        lock_files = find_lock_files(DEFAULT_INPUT_DIR)
        if not lock_files:
            print(f"Error: No lock files found in {DEFAULT_INPUT_DIR}")
            print(f"Please place yarn.lock or Gemfile.lock in the input_file/ directory")
            sys.exit(1)
        print(f"📂 Found {len(lock_files)} lock file(s) in {DEFAULT_INPUT_DIR}")
        for f in lock_files:
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
    
    # Initialize fetchers and detector
    registry_fetcher = RegistryFetcher()
    github_fetcher = GitHubFetcher(token=github_token if github_token else None)
    license_detector = LicenseDetector(similarity_threshold=similarity_threshold)
    
    # Check initial rate limit
    if github_token:
        rate_info = github_fetcher.check_rate_limit()
        print(f"📊 GitHub API rate limit: {rate_info['remaining']}/{rate_info['limit']}")
        print()
    
    # Process each lock file
    all_output_paths = []
    total_packages = 0
    all_errors: list[ProcessingError] = []
    total_cache_hits = 0
    
    with registry_fetcher, github_fetcher, cache:
        for lock_file_path in lock_files:
            # Get appropriate parser
            try:
                lock_parser = get_parser(lock_file_path)
                print(f"📦 Parsing {lock_file_path.name}...")
            except ValueError as e:
                print(f"Error: {e}")
                continue
            
            # Parse lock file
            packages = lock_parser.parse(lock_file_path)
            print(f"   Found {len(packages)} packages")
            print()
            
            # Build reverse dependency graph
            reverse_deps = build_reverse_dependency_graph(packages)
            
            # Process packages
            print("🔍 Fetching package information...")
            entries: list[SBOMEntry] = []
            errors: list[ProcessingError] = []
            cache_hits = 0
            
            for package in tqdm(packages, desc="Processing", unit="pkg"):
                entry, error, hit = process_package(
                    package,
                    registry_fetcher,
                    github_fetcher,
                    license_detector,
                    reverse_deps,
                    cache
                )
                entries.append(entry)
                if error:
                    errors.append(error)
                if hit:
                    cache_hits += 1
            
            print()
            
            # Write CSV output with lock file name prefix
            csv_writer = CSVWriter(output_dir=output_dir)
            prefix = lock_file_path.stem.replace(".", "_")  # yarn or Gemfile
            output_path = csv_writer.write(entries, filename_prefix=prefix)
            
            print(f"✅ SBOM report generated: {output_path}")
            print(f"   Total packages: {len(entries)}")
            if cache.enabled and cache_hits > 0:
                print(f"   Cache hits: {cache_hits} ({cache_hits * 100 // len(entries)}%)")
            
            all_output_paths.append(output_path)
            total_packages += len(entries)
            all_errors.extend(errors)
            total_cache_hits += cache_hits
            
            if len(lock_files) > 1:
                print()
                print("-" * 60)
                print()
    
    # Report errors
    if all_errors:
        print()
        print(f"⚠️  無法取得資訊的套件 ({len(all_errors)} 個):")
        print("-" * 50)
        for err in all_errors:
            print(f"  • {err.package_name}: {err.reason}")
    
    # Summary
    if len(lock_files) > 1:
        print()
        print("=" * 60)
        print(f"📋 Summary: Generated {len(all_output_paths)} SBOM report(s)")
        print(f"   Total packages processed: {total_packages}")
        if cache.enabled and total_cache_hits > 0:
            print(f"   Total cache hits: {total_cache_hits}")
        for path in all_output_paths:
            print(f"   - {path}")
    
    # Check remaining rate limit
    if github_token and github_fetcher.rate_limit_remaining is not None:
        print()
        print(f"📊 Remaining GitHub API calls: {github_fetcher.rate_limit_remaining}")
    
    # Show cache stats
    if cache.enabled:
        stats = cache.get_stats()
        print(f"📦 Cache entries: {stats['total_entries']}")


if __name__ == "__main__":
    main()

