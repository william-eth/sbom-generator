# Release Notes

## Version 3.0.0 (2026-01-13)

### New Features

#### Python requirements.txt Support
- **New parser**: Parse Python `requirements.txt` files to extract package dependencies
- **PyPI Registry**: Fetch repository URLs from PyPI JSON API
- **Version specifiers**: Support for `==`, `>=`, `<=`, `>`, `<`, `~=`, `!=` operators
- **Extras support**: Handle packages with extras like `package[extra1,extra2]`
- **Environment markers**: Parse and skip environment markers (`;` syntax)
- **Smart skip**: Automatically skip special pip options (`-r`, `-e`, `--index-url`, etc.)

#### Test Suite
- **Comprehensive testing**: 50 test cases covering models, parsers, and CSV output
- **Test fixtures**: Minimal, sanitized test files for all supported formats
- **pytest integration**: Full pytest configuration with markers support

#### CI/CD
- **GitHub Actions**: Automated testing on push and pull requests
- **Python matrix**: Tests run on Python 3.9, 3.10, 3.11, and 3.12
- **Dependency caching**: Faster CI runs with pip cache

### Improvements

- **Documentation**: Updated README with Python support and testing instructions
- **Directory structure**: Cleaner organization with dedicated test directories

### Technical Notes

- `requirements.txt` does not record dependency relationships
- All packages in requirements.txt are marked as `[直接依賴]` (direct dependency)
- For complete dependency tree analysis, `poetry.lock` and `Pipfile.lock` support is planned

---

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
