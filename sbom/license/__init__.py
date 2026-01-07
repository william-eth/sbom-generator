"""
License detection and validation module.
"""

from .detector import LicenseDetector
from .templates import GITHUB_LICENSE_TEMPLATES, LICENSE_PATTERNS

__all__ = ["LicenseDetector", "GITHUB_LICENSE_TEMPLATES", "LICENSE_PATTERNS"]

