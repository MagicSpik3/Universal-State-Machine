"""
Canonical Survey Logic Model (CSLM) Package

This is the authoritative, language-agnostic representation of survey logic.

ARCHITECTURAL GUARANTEE:
------------------------
This package contains ZERO knowledge of:
    - R code generation
    - SPSS syntax
    - Execution semantics
    - Language-specific idioms

This package defines SURVEY STRUCTURE only.

All transformations happen in external layers.
All backends consume this model unchanged.
"""

__version__ = "0.1.0"
