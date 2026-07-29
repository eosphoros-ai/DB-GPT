"""Code graph schema definitions.

Defines node types, edge types, and confidence levels for
the code repository knowledge graph.
"""

from enum import Enum


class CodeNodeType(str, Enum):
    """Types of nodes in the code knowledge graph."""

    REPOSITORY = "repository"
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"


class CodeEdgeType(str, Enum):
    """Types of edges in the code knowledge graph."""

    CONTAINS = "contains"
    IMPORTS = "imports"
    CALLS = "calls"
    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    REFERENCES = "references"


class EdgeConfidence(str, Enum):
    """Confidence level of an edge in the code knowledge graph.

    EXTRACTED: Directly observed in the AST (same-file calls, imports,
    inheritance).
    INFERRED: Derived through cross-file resolution without direct import
    evidence.
    AMBIGUOUS: Uncertain resolution, multiple candidates exist.
    """

    EXTRACTED = "EXTRACTED"
    INFERRED = "INFERRED"
    AMBIGUOUS = "AMBIGUOUS"
