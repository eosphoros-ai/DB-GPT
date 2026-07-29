"""Shared tree-sitter utilities for code splitting and graph extraction.

Extracted from code_splitter.py so both CodeTextSplitter and
CodeASTGraphExtractor can reuse the same parser creation and
AST node name/import extraction logic.
"""

import logging
import os
from typing import Dict, List

logger = logging.getLogger(__name__)

# AST node types that represent meaningful code boundaries per language
LANGUAGE_NODE_TYPES: Dict[str, List[str]] = {
    "python": [
        "function_definition",
        "class_definition",
    ],
    "java": [
        "method_declaration",
        "class_declaration",
        "interface_declaration",
        "constructor_declaration",
    ],
    "javascript": [
        "function_declaration",
        "class_declaration",
        "method_definition",
        "export_statement",
    ],
    "typescript": [
        "function_declaration",
        "class_declaration",
        "method_definition",
        "interface_declaration",
        "export_statement",
    ],
    "go": [
        "function_declaration",
        "method_declaration",
        "type_declaration",
    ],
    "rust": [
        "function_item",
        "impl_item",
        "struct_item",
        "enum_item",
        "trait_item",
    ],
    "c": [
        "function_definition",
        "struct_specifier",
        "enum_specifier",
    ],
    "cpp": [
        "function_definition",
        "class_specifier",
        "struct_specifier",
        "namespace_definition",
    ],
}

# Maps language names to tree-sitter grammar module names
GRAMMAR_MODULES: Dict[str, str] = {
    "python": "tree_sitter_python",
    "java": "tree_sitter_java",
    "javascript": "tree_sitter_javascript",
    "typescript": "tree_sitter_typescript",
    "go": "tree_sitter_go",
    "rust": "tree_sitter_rust",
    "c": "tree_sitter_c",
    "cpp": "tree_sitter_cpp",
}


def get_parser(language: str):
    """Create a tree-sitter parser for the given language.

    Requires tree-sitter>=0.21 and the corresponding grammar package.
    """
    try:
        import tree_sitter
    except ImportError:
        raise ImportError(
            "tree-sitter is required for code splitting. "
            "Install with: pip install tree-sitter"
        )

    module_name = GRAMMAR_MODULES.get(language)
    if not module_name:
        raise ValueError(f"Unsupported language for AST parsing: {language}")

    try:
        import importlib

        grammar_module = importlib.import_module(module_name)
    except ImportError:
        raise ImportError(
            f"tree-sitter grammar for {language} not found. "
            f"Install with: pip install tree-sitter-{language}"
        )

    # TypeScript has a special module structure: it exports
    # language_typescript() and language_tsx() instead of a single language()
    if language == "typescript":
        lang = tree_sitter.Language(grammar_module.language_typescript())
    elif language in ("tsx", "typescript_tsx"):
        lang = tree_sitter.Language(grammar_module.language_tsx())
    elif hasattr(grammar_module, "language"):
        # tree-sitter 0.21+ API (Python, Java, Go, Rust, C, C++)
        lang = tree_sitter.Language(grammar_module.language())
    else:
        # Fallback for older API
        lang = tree_sitter.Language(grammar_module.LANGUAGE)

    parser = tree_sitter.Parser(lang)
    return parser


def extract_name(node) -> str:
    """Extract the symbol name from an AST node."""
    for child in node.children:
        if child.type in (
            "identifier",
            "name",
            "type_identifier",
            "field_identifier",
            "property_identifier",
        ):
            return child.text.decode("utf-8")
        # For class/function with complex names
        if child.type == "function_declarator":
            return extract_name(child)
    return ""


def extract_imports(source_bytes: bytes, tree) -> str:
    """Extract import/include statements from the top of the file."""
    import_types = {
        "import_statement",
        "import_from_statement",  # Python
        "import_declaration",  # Java, Go
        "import_clause",
        "import_specifier",  # JS/TS
        "preproc_include",  # C/C++
        "use_declaration",  # Rust
    }
    imports = []
    for node in tree.root_node.children:
        if node.type in import_types:
            imports.append(
                source_bytes[node.start_byte : node.end_byte].decode("utf-8")
            )
        # Also capture package declarations
        if node.type in ("package_declaration", "package_clause"):
            imports.append(
                source_bytes[node.start_byte : node.end_byte].decode("utf-8")
            )
    return "\n".join(imports)


def get_language_from_extension(file_path: str) -> str:
    """Infer programming language from file extension."""
    ext_map = {
        ".py": "python",
        ".java": "java",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".hpp": "cpp",
        ".hh": "cpp",
    }
    _, ext = os.path.splitext(file_path)
    return ext_map.get(ext.lower(), "")
