# SBOM Generator

[繁體中文版本](README.zh-TW.md)

A tool for generating Software Bill of Materials (SBOM) reports. Extracts package dependencies, repository URLs, and license information from lock files and Dockerfiles.

## Features

- ✅ Supports multiple package managers (see [Supported Types](#supported-types))
- ✅ Builds complete dependency graphs
- ✅ Queries repository URLs from npm/RubyGems/PyPI registries
- ✅ Fetches license information via GitHub API and Debian Sources API
- ✅ Validates license content against standard templates
- ✅ Outputs UTF-8 with BOM CSV files (Excel compatible)
- ✅ Displays processing progress
- ✅ Detailed error reporting

## Supported Types

### Application Packages

| Language | Package Manager | File | Registry |
|----------|----------------|------|----------|
| JavaScript / Node.js | Yarn | `yarn.lock` | npm Registry |
| Ruby | Bundler | `Gemfile.lock` | RubyGems |
| Python | pip | `requirements.txt` | PyPI |

### OS System Packages

| OS Type | Package Manager | Input File | Data Source |
|---------|----------------|------------|-------------|
| Debian / Ubuntu | APT | `Dockerfile` | Debian Sources API / Tracker |

### Planned Support (Future)

| Type | Package Manager | File | Status |
|------|----------------|------|--------|
| JavaScript / Node.js | npm | `package-lock.json` | 🔜 Planned |
| JavaScript / Node.js | pnpm | `pnpm-lock.yaml` | 🔜 Planned |
| Python | Poetry | `poetry.lock` | 🔜 Planned |
| Python | Pipenv | `Pipfile.lock` | 🔜 Planned |
| Python | uv | `uv.lock` | 🔜 Planned |
| PHP | Composer | `composer.lock` | 🔜 Planned |
| Alpine Linux | APK | `Dockerfile` | 🔜 Planned |

## Requirements

- Python 3.9+
- Internet connection (for querying npm/RubyGems/PyPI registries and GitHub API)

## Installation

```bash
# 1. Clone or download this project
cd sbom-generator

# 2. Create virtual environment
python3 -m venv venv

# 3. Activate virtual environment
source venv/bin/activate  # macOS/Linux
# or
.\venv\Scripts\activate   # Windows

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure GitHub Token (recommended)
cp config.yaml.example config.yaml
# Edit config.yaml and add your GitHub Token
```

## Configuration

### GitHub Token (Recommended)

To avoid API rate limit restrictions, we recommend setting up a GitHub Personal Access Token:

| Status | Rate Limit |
|--------|-----------|
| No Token | 60 requests/hour |
| With Token | 5,000 requests/hour |

**Steps to get a Token:**

1. Go to [GitHub Settings > Tokens](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Select scope: `public_repo`
4. Copy the token and paste it into `config.yaml`

```yaml
# config.yaml
GITHUB_TOKEN: "your_github_token_here"
LICENSE_SIMILARITY_THRESHOLD: 0.9
```

## Directory Structure

```
sbom-generator/
├── .github/workflows/   # 🔄 GitHub Actions CI/CD
│   └── test.yml         # Test workflow
├── input_file/          # 📥 Place your lock files or Dockerfiles here
│   ├── yarn.lock
│   ├── package.json     # (Optional) For identifying direct dependencies
│   ├── Gemfile.lock
│   ├── requirements.txt # Python pip dependencies file
│   └── Dockerfile       # Dockerfile (Debian/Ubuntu supported)
├── output_file/         # 📤 Generated CSV reports
│   ├── yarn_sbom_app_yyyymmdd_hhmmss.csv         # Application packages
│   ├── requirements_sbom_app_yyyymmdd_hhmmss.csv # Python packages
│   └── Dockerfile_sbom_os_yyyymmdd_hhmmss.csv    # OS system packages
├── tests/               # 🧪 Test code
│   ├── fixtures/        # Test fixture files
│   ├── test_models.py   # Data model tests
│   ├── test_parsers.py  # Parser tests
│   └── test_output.py   # CSV output tests
├── config.yaml          # Configuration file (copy from config.yaml.example)
├── config.yaml.example  # Configuration template
├── main.py              # Main program
├── requirements.txt     # Python dependencies (for this tool)
└── sbom/                # Program modules
```

### About package.json (Optional)

For `yarn.lock` files, you can optionally place the project's `package.json` in the same directory:

| With package.json | Without package.json |
|-------------------|---------------------|
| ✅ Can identify direct dependencies (marked as `[Direct Dependency]`) | ⚠️ Cannot identify direct dependencies |
| ✅ Shows which packages reference each package | ✅ Shows which packages reference each package |

**Recommendation**: If you need to distinguish between direct and transitive dependencies in the report, place `package.json` alongside `yarn.lock`.

### About requirements.txt

Python's `requirements.txt` does not contain dependency relationship information, therefore:

| Feature | Description |
|---------|-------------|
| Direct Dependencies | All packages in the file are marked as `[Direct Dependency]` |
| Transitive Dependencies | Cannot be identified (requirements.txt doesn't record dependency tree) |
| Version Info | Extracted from version specifiers (e.g., `>=2.28.0` → `2.28.0`) |

**Note**: For complete dependency tree analysis, consider using `poetry.lock` or `Pipfile.lock` (planned for future support).

## Usage

### Basic Usage

```bash
# Activate virtual environment
source venv/bin/activate

# Method 1: Process all files in input_file/ directory
python main.py

# Method 2: Process a specific file
python main.py input_file/yarn.lock
python main.py input_file/Gemfile.lock
python main.py input_file/requirements.txt
python main.py input_file/Dockerfile

# Method 3: Process file from any path
python main.py /path/to/your/project/yarn.lock
python main.py /path/to/your/project/requirements.txt
python main.py /path/to/your/project/Dockerfile
```

### Advanced Options

```bash
# Specify output directory
python main.py --output ./my_reports

# Specify configuration file
python main.py --config /path/to/config.yaml

# Show help
python main.py --help
```

### Cache Options

The tool caches API responses to speed up subsequent runs:

```bash
# Use cache (default behavior)
python main.py --cache

# Ignore cache and fetch fresh data
python main.py --no-cache

# Clear cache and exit
python main.py --clear-cache
```

**Cache Details:**
- Cache file: `sbom_cache.json` (in project root)
- Cache expiry: 7 days
- First run: Fetches all data from APIs
- Subsequent runs: Uses cached data (much faster)

## Output Format

The generated CSV files are categorized into two types:

### Application Packages (`*_sbom_app_*.csv`)

| Column | Description |
|--------|-------------|
| Package Name | Package name |
| Referenced By | Which packages reference this one (`[Direct Dependency]` means directly used by project) |
| Repo URL | GitHub Repository URL |
| License Name | License name (using [GitHub official SPDX ID](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository#searching-github-by-license-type)) |
| License URL | GitHub link to the license file |
| Remarks | Exception notes (non-standard license, non-GitHub source, unable to fetch, etc.) |

### OS System Packages (`*_sbom_os_*.csv`)

| Column | Description |
|--------|-------------|
| Package Name | Package name |
| Install Source | `[Direct Dependency]` indicates explicitly installed in Dockerfile |
| Package URL | Debian Tracker URL |
| License Name | License list parsed from debian/copyright |
| License URL | debian/copyright file link |
| VCS URL | Version Control System URL (e.g., Salsa GitLab) |
| Remarks | Additional notes |

### Example Output

**Application Packages:**
```csv
Package Name,Referenced By,Repo URL,License Name,License URL,Remarks
express,[Direct Dependency],https://github.com/expressjs/express,MIT License,https://github.com/expressjs/express/blob/master/LICENSE,
lodash,[Direct Dependency],https://github.com/lodash/lodash,Other,https://github.com/lodash/lodash/blob/main/LICENSE,
```

**OS System Packages:**
```csv
Package Name,Install Source,Package URL,License Name,License URL,VCS URL,Remarks
imagemagick,[Direct Dependency],https://tracker.debian.org/pkg/imagemagick,"ImageMagick
GPL-2.0-or-later",https://sources.debian.org/.../copyright,https://salsa.debian.org/debian/imagemagick,
```

## Supported License Types

This tool supports [GitHub officially defined license types](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository#searching-github-by-license-type):

| License | SPDX ID |
|---------|---------|
| Academic Free License v3.0 | `AFL-3.0` |
| Apache License 2.0 | `Apache-2.0` |
| Artistic License 2.0 | `Artistic-2.0` |
| Boost Software License 1.0 | `BSL-1.0` |
| BSD 2-Clause "Simplified" License | `BSD-2-Clause` |
| BSD 3-Clause "New" or "Revised" License | `BSD-3-Clause` |
| BSD 3-Clause Clear License | `BSD-3-Clause-Clear` |
| BSD 4-Clause "Original" or "Old" License | `BSD-4-Clause` |
| BSD Zero Clause License | `0BSD` |
| Creative Commons License Family | `CC` |
| Creative Commons Zero v1.0 Universal | `CC0-1.0` |
| Creative Commons Attribution 4.0 | `CC-BY-4.0` |
| Creative Commons Attribution ShareAlike 4.0 | `CC-BY-SA-4.0` |
| Do What The F*ck You Want To Public License | `WTFPL` |
| Educational Community License v2.0 | `ECL-2.0` |
| Eclipse Public License 1.0 | `EPL-1.0` |
| Eclipse Public License 2.0 | `EPL-2.0` |
| European Union Public License 1.1 | `EUPL-1.1` |
| GNU Affero General Public License v3.0 | `AGPL-3.0` |
| GNU General Public License Family | `GPL` |
| GNU General Public License v2.0 | `GPL-2.0` |
| GNU General Public License v3.0 | `GPL-3.0` |
| GNU Lesser General Public License Family | `LGPL` |
| GNU Lesser General Public License v2.1 | `LGPL-2.1` |
| GNU Lesser General Public License v3.0 | `LGPL-3.0` |
| ISC License | `ISC` |
| LaTeX Project Public License v1.3c | `LPPL-1.3c` |
| Microsoft Public License | `MS-PL` |
| MIT License | `MIT` |
| Mozilla Public License 2.0 | `MPL-2.0` |
| Open Software License 3.0 | `OSL-3.0` |
| PostgreSQL License | `PostgreSQL` |
| SIL Open Font License 1.1 | `OFL-1.1` |
| University of Illinois/NCSA Open Source License | `NCSA` |
| The Unlicense | `Unlicense` |
| zLib License | `Zlib` |

## Remarks Explanation

The "Remarks" column in the CSV may contain the following information:

| Remarks | Description |
|---------|-------------|
| `Non-standard (MIT)` | License identified as MIT, but content differs from standard template |
| `Non-GitHub source` | Repository is not hosted on GitHub |
| `Unable to fetch` | Cannot retrieve information from registry or GitHub |
| `License type could not be determined` | GitHub cannot identify the license type |
| `Package not found in Debian sources` | Package not found in Debian Sources API |

## Development

### Running Tests

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v
```

### Test Fixtures

Test fixture files are located in `tests/fixtures/`:
- `yarn.lock` - JavaScript/Node.js test file
- `package.json` - npm direct dependency definition
- `Gemfile.lock` - Ruby test file
- `requirements.txt` - Python test file
- `Dockerfile` - Debian-based Dockerfile test file

## License

MIT License
