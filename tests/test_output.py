"""
Tests for SBOM CSV output writer.
"""

import csv
import pytest
import tempfile
from pathlib import Path

from sbom.output import CSVWriter
from sbom.models import SBOMCategory, SBOMEntry


class TestCSVWriter:
    """Tests for CSVWriter class."""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary directory for output files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sample_app_entries(self) -> list[SBOMEntry]:
        """Sample application-level SBOM entries for testing."""
        return [
            SBOMEntry(
                package_name="express",
                referenced_by="[直接依賴]",
                repo_url="https://github.com/expressjs/express",
                license_name="MIT License",
                license_url="https://github.com/expressjs/express/blob/master/LICENSE",
                remark="",
            ),
            SBOMEntry(
                package_name="lodash",
                referenced_by="express, webpack",
                repo_url="https://github.com/lodash/lodash",
                license_name="MIT License",
                license_url="https://github.com/lodash/lodash/blob/main/LICENSE",
                remark="",
            ),
            SBOMEntry(
                package_name="unknown-pkg",
                referenced_by="[直接依賴]",
                repo_url="",
                license_name="",
                license_url="",
                remark="無法取得",
            ),
        ]

    @pytest.fixture
    def sample_os_entries(self) -> list[SBOMEntry]:
        """Sample OS-level SBOM entries for testing."""
        return [
            SBOMEntry(
                package_name="curl",
                referenced_by="[直接依賴]",
                repo_url="https://tracker.debian.org/pkg/curl",
                license_name="MIT",
                license_url="https://sources.debian.org/src/curl/latest/COPYING",
                vcs_url="https://salsa.debian.org/debian/curl",
                remark="",
            ),
            SBOMEntry(
                package_name="git",
                referenced_by="[直接依賴]",
                repo_url="https://tracker.debian.org/pkg/git",
                license_name="GPL-2.0",
                license_url="https://sources.debian.org/src/git/latest/COPYING",
                vcs_url="https://salsa.debian.org/debian/git",
                remark="",
            ),
        ]

    def test_csv_writer_creates_output_directory(self, temp_output_dir: Path):
        """Test that CSVWriter creates output directory if it doesn't exist."""
        new_dir = temp_output_dir / "new_subdir"
        assert not new_dir.exists()
        
        writer = CSVWriter(output_dir=new_dir)
        assert new_dir.exists()

    def test_write_application_csv(
        self,
        temp_output_dir: Path,
        sample_app_entries: list[SBOMEntry]
    ):
        """Test writing application-level SBOM to CSV."""
        writer = CSVWriter(output_dir=temp_output_dir)
        output_path = writer.write(
            entries=sample_app_entries,
            filename="test_app.csv",
            category=SBOMCategory.APPLICATION
        )
        
        assert output_path.exists()
        assert output_path.name == "test_app.csv"
        
        # Read and verify content
        with open(output_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        # Verify headers
        assert rows[0] == CSVWriter.APPLICATION_HEADERS
        
        # Verify data rows
        assert len(rows) == 4  # 1 header + 3 data rows
        assert rows[1][0] == "express"
        assert rows[1][1] == "[直接依賴]"
        assert rows[2][0] == "lodash"
        assert rows[3][5] == "無法取得"  # remark column

    def test_write_os_system_csv(
        self,
        temp_output_dir: Path,
        sample_os_entries: list[SBOMEntry]
    ):
        """Test writing OS-level SBOM to CSV."""
        writer = CSVWriter(output_dir=temp_output_dir)
        output_path = writer.write(
            entries=sample_os_entries,
            filename="test_os.csv",
            category=SBOMCategory.OS_SYSTEM
        )
        
        assert output_path.exists()
        
        # Read and verify content
        with open(output_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        # Verify headers (OS has VCS URL column)
        assert rows[0] == CSVWriter.OS_SYSTEM_HEADERS
        assert "VCS URL" in rows[0]
        
        # Verify data rows
        assert len(rows) == 3  # 1 header + 2 data rows
        assert rows[1][0] == "curl"
        assert rows[1][5] == "https://salsa.debian.org/debian/curl"  # vcs_url

    def test_utf8_bom_encoding(
        self,
        temp_output_dir: Path,
        sample_app_entries: list[SBOMEntry]
    ):
        """Test that CSV file has UTF-8 BOM for Excel compatibility."""
        writer = CSVWriter(output_dir=temp_output_dir)
        output_path = writer.write(
            entries=sample_app_entries,
            filename="test_bom.csv",
            category=SBOMCategory.APPLICATION
        )
        
        # Read raw bytes to check BOM
        with open(output_path, "rb") as f:
            first_bytes = f.read(3)
        
        # UTF-8 BOM is EF BB BF
        assert first_bytes == b'\xef\xbb\xbf'

    def test_auto_generated_filename_app(
        self,
        temp_output_dir: Path,
        sample_app_entries: list[SBOMEntry]
    ):
        """Test auto-generated filename for application packages."""
        writer = CSVWriter(output_dir=temp_output_dir)
        output_path = writer.write(
            entries=sample_app_entries,
            filename_prefix="yarn",
            category=SBOMCategory.APPLICATION
        )
        
        # Filename should be: yarn_sbom_app_YYYYMMDD_HHMMSS.csv
        assert output_path.name.startswith("yarn_sbom_app_")
        assert output_path.name.endswith(".csv")

    def test_auto_generated_filename_os(
        self,
        temp_output_dir: Path,
        sample_os_entries: list[SBOMEntry]
    ):
        """Test auto-generated filename for OS packages."""
        writer = CSVWriter(output_dir=temp_output_dir)
        output_path = writer.write(
            entries=sample_os_entries,
            filename_prefix="Dockerfile",
            category=SBOMCategory.OS_SYSTEM
        )
        
        # Filename should be: Dockerfile_sbom_os_YYYYMMDD_HHMMSS.csv
        assert output_path.name.startswith("Dockerfile_sbom_os_")
        assert output_path.name.endswith(".csv")

    def test_chinese_characters_in_csv(self, temp_output_dir: Path):
        """Test that Chinese characters are correctly written."""
        entries = [
            SBOMEntry(
                package_name="測試套件",
                referenced_by="[直接依賴]",
                repo_url="https://github.com/test/test",
                license_name="MIT 授權",
                license_url="",
                remark="這是備註",
            ),
        ]
        
        writer = CSVWriter(output_dir=temp_output_dir)
        output_path = writer.write(
            entries=entries,
            filename="test_chinese.csv",
            category=SBOMCategory.APPLICATION
        )
        
        # Read and verify Chinese content
        with open(output_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        assert rows[1][0] == "測試套件"
        assert rows[1][1] == "[直接依賴]"
        assert rows[1][3] == "MIT 授權"
        assert rows[1][5] == "這是備註"

    def test_special_characters_in_csv(self, temp_output_dir: Path):
        """Test that special characters (commas, quotes) are handled correctly."""
        entries = [
            SBOMEntry(
                package_name="pkg-with-comma",
                referenced_by="dep1, dep2, dep3",
                repo_url="https://github.com/test/test",
                license_name='BSD 3-Clause "New" or "Revised" License',
                license_url="",
                remark="",
            ),
        ]
        
        writer = CSVWriter(output_dir=temp_output_dir)
        output_path = writer.write(
            entries=entries,
            filename="test_special.csv",
            category=SBOMCategory.APPLICATION
        )
        
        # Read and verify special characters are preserved
        with open(output_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        assert rows[1][1] == "dep1, dep2, dep3"
        assert rows[1][3] == 'BSD 3-Clause "New" or "Revised" License'

    def test_empty_entries(self, temp_output_dir: Path):
        """Test writing CSV with no entries."""
        writer = CSVWriter(output_dir=temp_output_dir)
        output_path = writer.write(
            entries=[],
            filename="test_empty.csv",
            category=SBOMCategory.APPLICATION
        )
        
        # Read and verify only headers exist
        with open(output_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        assert len(rows) == 1  # Only headers
        assert rows[0] == CSVWriter.APPLICATION_HEADERS

    def test_application_headers_order(self):
        """Test that application headers are in correct order."""
        expected = [
            "套件名稱",
            "引用套件名稱",
            "套件 Repo URL",
            "License 名稱",
            "License URL",
            "備註",
        ]
        assert CSVWriter.APPLICATION_HEADERS == expected

    def test_os_system_headers_order(self):
        """Test that OS system headers are in correct order."""
        expected = [
            "套件名稱",
            "安裝來源",
            "套件 URL",
            "License 名稱",
            "License URL",
            "VCS URL",
            "備註",
        ]
        assert CSVWriter.OS_SYSTEM_HEADERS == expected

    def test_from_dict_list(self):
        """Test converting dictionary list to SBOMEntry objects."""
        data = [
            {
                "package_name": "express",
                "referenced_by": "[直接依賴]",
                "repo_url": "https://github.com/expressjs/express",
                "license_name": "MIT",
                "license_url": "https://example.com/LICENSE",
                "remark": "",
            },
            {
                "package_name": "lodash",
                "referenced_by": "express",
                "repo_url": "https://github.com/lodash/lodash",
                "license_name": "MIT",
                "license_url": "",
                "remark": "備註",
            },
        ]
        
        entries = CSVWriter.from_dict_list(data)
        
        assert len(entries) == 2
        assert entries[0].package_name == "express"
        assert entries[0].referenced_by == "[直接依賴]"
        assert entries[1].package_name == "lodash"
        assert entries[1].remark == "備註"
