# Release Notes

## Version 2.0.0 (2026-01-09)

### New Features

#### Dockerfile Support (Debian/Ubuntu)
- **OS-level package scanning**: Parse Dockerfiles to extract system packages installed via `apt-get install`
- **Debian package metadata**: Fetch license information from Debian Sources API and Tracker
- **VCS information**: Extract version control URLs (e.g., Salsa GitLab) for Debian packages
- **Binary to source mapping**: Automatically resolve binary package names to source packages for accurate license lookup
- **Multi-line ENV variable support**: Correctly parse complex Dockerfiles with multi-line environment variables

#### Separate SBOM Categories
- **Application-level SBOM** (`*_sbom_app_*.csv`): npm and RubyGems packages
- **OS-level SBOM** (`*_sbom_os_*.csv`): Debian/Ubuntu system packages with dedicated columns:
  - Package URL (Debian Tracker)
  - License names (full list, not summarized)
  - License URL (debian/copyright)
  - VCS URL (version control repository)

### Improvements

- **License display**: All licenses are now fully listed (separated by newlines) instead of summarized as "License + N others"
- **Caching**: Extended cache support for Debian source package mappings and VCS information
- **Progress display**: Improved progress bar for OS package processing

### Limitations

- **Alpine Linux (APK)**: Not yet supported. Dockerfiles using Alpine will return an error message
- **Other OS types**: CentOS, RHEL, Fedora are not supported in this release

---

## Version 1.0.0

### Features

#### Application Package Support
- **yarn.lock**: Parse Yarn lock files and fetch package info from npm Registry
- **Gemfile.lock**: Parse Bundler lock files and fetch package info from RubyGems

#### License Detection
- Fetch license information from GitHub API
- Validate license content against standard templates
- Support for all GitHub-recognized SPDX license identifiers

#### Output
- UTF-8 with BOM CSV files (Excel compatible)
- Dependency graph showing which packages depend on each other
- Direct vs transitive dependency identification

#### Performance
- File-based caching with 7-day expiration
- GitHub API rate limit handling (5,000 requests/hour with token)
- Progress bar display during processing
