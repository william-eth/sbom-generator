"""
License detector for validating license content against standard templates.
"""

import re
from difflib import SequenceMatcher
from typing import Optional

from ..models import LicenseInfo
from .templates import (
    GITHUB_LICENSE_TEMPLATES,
    LICENSE_PATTERNS,
    VALID_SPDX_IDS,
)


class LicenseDetector:
    """
    Detects and validates licenses against standard templates.
    
    Uses pattern matching and similarity comparison to verify
    that license content matches the claimed license type.
    """
    
    def __init__(self, similarity_threshold: float = 0.9):
        """
        Initialize license detector.
        
        Args:
            similarity_threshold: Minimum similarity ratio (0.0-1.0) for
                                  a license to be considered standard.
                                  Default is 0.9 (90%).
        """
        self.similarity_threshold = similarity_threshold
    
    def validate(self, license_info: LicenseInfo) -> tuple[bool, str]:
        """
        Validate that license content matches the claimed license type.
        
        Args:
            license_info: LicenseInfo object with spdx_id and content.
            
        Returns:
            Tuple of (is_standard, remark).
            - is_standard: True if license content matches template.
            - remark: Description of any issues found.
        """
        spdx_id = license_info.spdx_id
        content = license_info.content
        
        # Handle special cases
        if not spdx_id or spdx_id == "NOASSERTION":
            # GitHub couldn't identify the license
            if content:
                # Try to detect license type from content
                detected = self.detect_license_type(content)
                if detected:
                    return True, f"Detected as {detected} from content"
                
                # Try to find license mentions in content
                mentions = self.extract_license_mentions(content)
                if mentions:
                    return False, f"License type could not be determined. Content mentions: {mentions}"
            
            return False, "License type could not be determined"
        
        # Check if SPDX ID is in GitHub's official list
        base_id = self._get_base_license_id(spdx_id)
        if spdx_id in VALID_SPDX_IDS or base_id in VALID_SPDX_IDS:
            # GitHub identified a valid SPDX ID - trust this result
            # Only do content validation if we want to be extra strict
            if content and spdx_id in LICENSE_PATTERNS:
                is_valid, missing = self._validate_patterns(spdx_id, content)
                if not is_valid:
                    # Log as info but still consider it standard
                    # since GitHub's API already identified it
                    return True, f"Note: Some standard phrases not found, but GitHub identified as {spdx_id}"
            return True, ""
        
        # SPDX ID not in GitHub's official list
        return False, f"Non-standard SPDX ID: {spdx_id}"
    
    def _validate_patterns(self, spdx_id: str, content: str) -> tuple[bool, list[str]]:
        """
        Validate license content against known patterns.
        
        Args:
            spdx_id: The SPDX license identifier.
            content: The license file content.
            
        Returns:
            Tuple of (is_valid, missing_patterns).
        """
        patterns = LICENSE_PATTERNS.get(spdx_id, [])
        if not patterns:
            return True, []
        
        # Normalize content for comparison
        normalized = self._normalize_text(content)
        
        # Check each pattern
        missing = []
        matched = 0
        
        for pattern in patterns:
            normalized_pattern = self._normalize_text(pattern)
            if normalized_pattern in normalized:
                matched += 1
            else:
                missing.append(pattern)
        
        # Require at least threshold percentage of patterns to match
        if len(patterns) > 0:
            match_ratio = matched / len(patterns)
            if match_ratio >= self.similarity_threshold:
                return True, []
        
        return False, missing
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        # Convert to lowercase
        text = text.lower()
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove punctuation variations
        text = re.sub(r'[""'']', '"', text)
        return text.strip()
    
    def _get_base_license_id(self, spdx_id: str) -> str:
        """
        Get base license ID from variants.
        
        Examples:
        - "MIT-0" -> "MIT"
        - "GPL-3.0-only" -> "GPL-3.0"
        - "Apache-2.0" -> "Apache-2.0"
        """
        # Common suffixes to strip
        suffixes = ["-only", "-or-later", "+", "-0"]
        result = spdx_id
        for suffix in suffixes:
            if result.endswith(suffix):
                result = result[:-len(suffix)]
        return result
    
    def detect_license_type(self, content: str) -> Optional[str]:
        """
        Attempt to detect license type from content.
        
        Args:
            content: License file content.
            
        Returns:
            SPDX ID if detected, None otherwise.
        """
        if not content:
            return None
        
        normalized = self._normalize_text(content)
        
        # Check patterns for each known license
        best_match = None
        best_score = 0
        
        for spdx_id, patterns in LICENSE_PATTERNS.items():
            matched = 0
            for pattern in patterns:
                if self._normalize_text(pattern) in normalized:
                    matched += 1
            
            if len(patterns) > 0:
                score = matched / len(patterns)
                if score > best_score and score >= 0.5:  # At least 50% match
                    best_score = score
                    best_match = spdx_id
        
        return best_match
    
    def extract_license_mentions(self, content: str) -> str:
        """
        Extract license type mentions from content.
        
        Searches for common license keywords and returns what the content
        claims the license to be.
        
        Args:
            content: License file content.
            
        Returns:
            String describing mentioned licenses, or empty string if none found.
        """
        if not content:
            return ""
        
        mentions = []
        content_lower = content.lower()
        
        # Common license patterns to search for
        license_keywords = [
            # BSD variants
            (r'\b2-clause\s+bsd\b', 'BSD-2-Clause'),
            (r'\bbsd\s*2-clause\b', 'BSD-2-Clause'),
            (r'\b3-clause\s+bsd\b', 'BSD-3-Clause'),
            (r'\bbsd\s*3-clause\b', 'BSD-3-Clause'),
            (r'\bbsdl\b', 'BSD License'),
            (r'\bbsd\s+license\b', 'BSD License'),
            
            # MIT
            (r'\bmit\s+license\b', 'MIT'),
            (r'\bunder\s+the\s+mit\b', 'MIT'),
            
            # Apache
            (r'\bapache\s+license[,\s]+version\s+2\.0\b', 'Apache-2.0'),
            (r'\bapache\s*2\.0\b', 'Apache-2.0'),
            (r'\bapache\s+license\b', 'Apache License'),
            
            # GPL
            (r'\bgnu\s+general\s+public\s+license\s+v3\b', 'GPL-3.0'),
            (r'\bgpl\s*v?3\b', 'GPL-3.0'),
            (r'\bgnu\s+general\s+public\s+license\s+v2\b', 'GPL-2.0'),
            (r'\bgpl\s*v?2\b', 'GPL-2.0'),
            (r'\bgpl\s+license\b', 'GPL'),
            
            # LGPL
            (r'\blgpl\b', 'LGPL'),
            (r'\blesser\s+general\s+public\s+license\b', 'LGPL'),
            
            # Ruby specific
            (r'\bruby\s+license\b', 'Ruby License'),
            (r"\bruby'?s?\s+own\s+license\b", 'Ruby License'),
            
            # ISC
            (r'\bisc\s+license\b', 'ISC'),
            
            # MPL
            (r'\bmozilla\s+public\s+license\b', 'MPL'),
            
            # Creative Commons
            (r'\bcc0\b', 'CC0'),
            (r'\bcreative\s+commons\b', 'Creative Commons'),
            
            # Unlicense
            (r'\bunlicense\b', 'Unlicense'),
            
            # Public Domain
            (r'\bpublic\s+domain\b', 'Public Domain'),
        ]
        
        for pattern, license_name in license_keywords:
            if re.search(pattern, content_lower):
                if license_name not in mentions:
                    mentions.append(license_name)
        
        # Return unique mentions
        if mentions:
            return ', '.join(mentions)
        
        return ""
    
    def get_official_name(self, spdx_id: str) -> str:
        """
        Get the official license name from SPDX ID.
        
        Args:
            spdx_id: The SPDX license identifier.
            
        Returns:
            Official license name or the SPDX ID if not found.
        """
        return GITHUB_LICENSE_TEMPLATES.get(spdx_id, spdx_id)
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity ratio between two texts.
        
        Args:
            text1: First text.
            text2: Second text.
            
        Returns:
            Similarity ratio between 0.0 and 1.0.
        """
        normalized1 = self._normalize_text(text1)
        normalized2 = self._normalize_text(text2)
        
        return SequenceMatcher(None, normalized1, normalized2).ratio()

