"""
CSV writer for SBOM reports.
Outputs UTF-8 with BOM for Excel compatibility.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models import SBOMCategory, SBOMEntry


class CSVWriter:
    """Writes SBOM entries to CSV file."""
    
    # CSV column headers for different SBOM categories
    APPLICATION_HEADERS = [
        "套件名稱",
        "引用套件名稱",
        "套件 Repo URL",
        "License 名稱",
        "License URL",
        "備註",
    ]
    
    OS_SYSTEM_HEADERS = [
        "套件名稱",
        "安裝來源",
        "套件 URL",
        "License 名稱",
        "License URL",
        "VCS URL",
        "備註",
    ]
    
    # Legacy headers (for backward compatibility)
    HEADERS = APPLICATION_HEADERS
    
    # UTF-8 BOM for Excel compatibility
    UTF8_BOM = "\ufeff"
    
    def __init__(self, output_dir: Optional[str | Path] = None):
        """
        Initialize CSV writer.
        
        Args:
            output_dir: Directory to write CSV files.
                        Defaults to current directory.
        """
        self.output_dir = Path(output_dir) if output_dir else Path.cwd()
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def write(
        self,
        entries: list[SBOMEntry],
        filename: Optional[str] = None,
        filename_prefix: Optional[str] = None,
        category: Optional[SBOMCategory] = None
    ) -> Path:
        """
        Write SBOM entries to CSV file.
        
        Args:
            entries: List of SBOMEntry objects to write.
            filename: Optional filename. Auto-generated if not provided.
            filename_prefix: Optional prefix for auto-generated filename.
            category: SBOM category for selecting appropriate headers.
            
        Returns:
            Path to the written CSV file.
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prefix = f"{filename_prefix}_" if filename_prefix else ""
            
            # Add category suffix for clarity
            if category == SBOMCategory.OS_SYSTEM:
                category_suffix = "_os"
            elif category == SBOMCategory.APPLICATION:
                category_suffix = "_app"
            else:
                category_suffix = ""
            
            filename = f"{prefix}sbom{category_suffix}_{timestamp}.csv"
        
        output_path = self.output_dir / filename
        
        # Select headers based on category
        if category == SBOMCategory.OS_SYSTEM:
            headers = self.OS_SYSTEM_HEADERS
        else:
            headers = self.APPLICATION_HEADERS
        
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            # Write UTF-8 BOM
            f.write(self.UTF8_BOM)
            
            writer = csv.writer(f)
            
            # Write headers
            writer.writerow(headers)
            
            # Write data rows
            for entry in entries:
                if category == SBOMCategory.OS_SYSTEM:
                    # OS-level packages include VCS URL column
                    writer.writerow([
                        entry.package_name,
                        entry.referenced_by,
                        entry.repo_url,
                        entry.license_name,
                        entry.license_url,
                        entry.vcs_url,
                        entry.remark,
                    ])
                else:
                    # Application-level packages
                    writer.writerow([
                        entry.package_name,
                        entry.referenced_by,
                        entry.repo_url,
                        entry.license_name,
                        entry.license_url,
                        entry.remark,
                    ])
        
        return output_path
    
    @classmethod
    def from_dict_list(cls, data: list[dict]) -> list[SBOMEntry]:
        """
        Convert list of dictionaries to SBOMEntry objects.
        
        Args:
            data: List of dictionaries with SBOM data.
            
        Returns:
            List of SBOMEntry objects.
        """
        entries = []
        for item in data:
            entries.append(SBOMEntry(
                package_name=item.get("package_name", ""),
                referenced_by=item.get("referenced_by", ""),
                repo_url=item.get("repo_url", ""),
                license_name=item.get("license_name", ""),
                license_url=item.get("license_url", ""),
                remark=item.get("remark", ""),
            ))
        return entries

