"""
License templates and patterns based on GitHub's official license keywords.

Reference:
https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository#searching-github-by-license-type
"""

# GitHub official license keywords mapping
# Format: SPDX ID -> Full license name
GITHUB_LICENSE_TEMPLATES: dict[str, str] = {
    # Academic and permissive licenses
    "AFL-3.0": "Academic Free License v3.0",
    "Apache-2.0": "Apache License 2.0",
    "Artistic-2.0": "Artistic License 2.0",
    "BSL-1.0": "Boost Software License 1.0",
    
    # BSD variants
    "BSD-2-Clause": 'BSD 2-Clause "Simplified" License',
    "BSD-3-Clause": 'BSD 3-Clause "New" or "Revised" License',
    "BSD-3-Clause-Clear": "BSD 3-Clause Clear License",
    "BSD-4-Clause": 'BSD 4-Clause "Original" or "Old" License',
    "0BSD": "BSD Zero Clause License",
    
    # Creative Commons
    "CC": "Creative Commons License Family",
    "CC0-1.0": "Creative Commons Zero v1.0 Universal",
    "CC-BY-4.0": "Creative Commons Attribution 4.0",
    "CC-BY-SA-4.0": "Creative Commons Attribution ShareAlike 4.0",
    
    # Other permissive
    "WTFPL": "Do What The F*ck You Want To Public License",
    "ECL-2.0": "Educational Community License v2.0",
    "EPL-1.0": "Eclipse Public License 1.0",
    "EPL-2.0": "Eclipse Public License 2.0",
    "EUPL-1.1": "European Union Public License 1.1",
    
    # GNU licenses
    "AGPL-3.0": "GNU Affero General Public License v3.0",
    "GPL": "GNU General Public License Family",
    "GPL-2.0": "GNU General Public License v2.0",
    "GPL-3.0": "GNU General Public License v3.0",
    "LGPL": "GNU Lesser General Public License Family",
    "LGPL-2.1": "GNU Lesser General Public License v2.1",
    "LGPL-3.0": "GNU Lesser General Public License v3.0",
    
    # Other
    "ISC": "ISC License",
    "LPPL-1.3c": "LaTeX Project Public License v1.3c",
    "MS-PL": "Microsoft Public License",
    "MIT": "MIT License",
    "MPL-2.0": "Mozilla Public License 2.0",
    "OSL-3.0": "Open Software License 3.0",
    "PostgreSQL": "PostgreSQL License",
    "OFL-1.1": "SIL Open Font License 1.1",
    "NCSA": "University of Illinois/NCSA Open Source License",
    "Unlicense": "The Unlicense",
    "Zlib": "zLib License",
}

# Set of all valid SPDX IDs from GitHub
VALID_SPDX_IDS: set[str] = set(GITHUB_LICENSE_TEMPLATES.keys())

# License family mappings (for family-based searches)
LICENSE_FAMILIES: dict[str, list[str]] = {
    "CC": ["CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0"],
    "GPL": ["GPL-2.0", "GPL-3.0"],
    "LGPL": ["LGPL-2.1", "LGPL-3.0"],
}

# Key phrases for license content validation
# These are distinctive phrases that should appear in each license type
LICENSE_PATTERNS: dict[str, list[str]] = {
    "MIT": [
        "permission is hereby granted, free of charge",
        "the software is provided \"as is\"",
        "without warranty of any kind",
    ],
    "Apache-2.0": [
        "apache license",
        "version 2.0",
        "perpetual, worldwide, non-exclusive",
        "copyright license to reproduce",
    ],
    "GPL-2.0": [
        "gnu general public license",
        "version 2",
        "free software foundation",
        "either version 2 of the license",
    ],
    "GPL-3.0": [
        "gnu general public license",
        "version 3",
        "free software foundation",
        "everyone is permitted to copy",
    ],
    "BSD-2-Clause": [
        "redistribution and use in source and binary forms",
        "redistributions of source code must retain",
        "redistributions in binary form must reproduce",
    ],
    "BSD-3-Clause": [
        "redistribution and use in source and binary forms",
        "redistributions of source code must retain",
        "neither the name of",
        "may be used to endorse or promote",
    ],
    "ISC": [
        "permission to use, copy, modify, and/or distribute",
        "isc license",
    ],
    "LGPL-2.1": [
        "gnu lesser general public license",
        "version 2.1",
        "free software foundation",
    ],
    "LGPL-3.0": [
        "gnu lesser general public license",
        "version 3",
        "free software foundation",
    ],
    "MPL-2.0": [
        "mozilla public license",
        "version 2.0",
        "covered software is provided",
    ],
    "AGPL-3.0": [
        "gnu affero general public license",
        "version 3",
        "free software foundation",
        "remote network interaction",
    ],
    "Unlicense": [
        "this is free and unencumbered software",
        "released into the public domain",
    ],
    "CC0-1.0": [
        "creative commons",
        "cc0 1.0 universal",
        "public domain dedication",
    ],
    "Zlib": [
        "zlib license",
        "altered source versions must be plainly marked",
    ],
    "BSL-1.0": [
        "boost software license",
        "version 1.0",
    ],
}

