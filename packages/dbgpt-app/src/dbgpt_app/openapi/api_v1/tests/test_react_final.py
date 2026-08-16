"""Tests for the structured ReAct final-answer contract."""

import json

from dbgpt_app.openapi.api_v1.react_final import (
    MAX_CITATION_CHARS,
    MAX_CITATIONS,
    MAX_TOTAL_CITATION_CHARS,
    FinalAnswerAssembler,
    strip_legacy_references,
)


def test_code_and_navigation_tool_outputs_are_not_citations() -> None:
    assembler = FinalAnswerAssembler()
    source = "import pandas as pd\n" * 100
    generic_chunks = json.dumps(
        {"chunks": [{"output_type": "code", "content": source}]}
    )

    assembler.observe("execute_skill_script_file", {}, generic_chunks)
    assembler.observe("code_interpreter", {"code": source}, source)
    assembler.observe("kb_ls", {"path": "src"}, "Directory: src\n  main.py")
    assembler.observe("kb_glob", {"pattern": "*.py"}, "src/main.py")

    assert assembler.finalize("Analysis complete.").citations == ()


def test_kb_cat_becomes_a_structured_citation() -> None:
    assembler = FinalAnswerAssembler()
    assembler.observe(
        "kb_cat",
        {"path": "docs/design.md", "start_line": 4, "end_line": 12},
        "docs/design.md (markdown, 20 lines)\n"
        "     4 | The answer is supported by this design.\n"
        "     5 | More supporting detail.",
    )

    answer = assembler.finalize("The final answer.")

    assert answer.content == "The final answer."
    assert len(answer.citations) == 1
    payload = answer.to_sse_payload()
    assert payload == {
        "type": "final",
        "protocol_version": 2,
        "content": "The final answer.",
        "citations": [
            {
                "index": 1,
                "id": payload["citations"][0]["id"],
                "sourceName": "docs/design.md",
                "excerpt": (
                    "docs/design.md (markdown, 20 lines)\n"
                    "     4 | The answer is supported by this design.\n"
                    "     5 | More supporting detail."
                ),
                "score": None,
                "path": "docs/design.md",
                "url": None,
            }
        ],
    }


def test_single_string_tool_input_can_still_produce_a_valid_citation() -> None:
    assembler = FinalAnswerAssembler()
    assembler.observe(
        "kb_cat",
        "docs/design.md",
        "docs/design.md (markdown, 1 lines)\n"
        "     1 | Supporting content from the requested file.",
    )

    citations = assembler.finalize("Answer.").to_dict()["citations"]

    assert len(citations) == 1
    assert citations[0]["sourceName"] == "docs/design.md"


def test_failed_or_malformed_knowledge_results_fail_closed() -> None:
    assembler = FinalAnswerAssembler()

    assembler.observe("knowledge_retrieve", {"query": "x"}, "not json")
    assembler.observe(
        "knowledge_retrieve",
        {"query": "x"},
        json.dumps({"chunks": "not-a-list"}),
    )
    assembler.observe(
        "kb_cat",
        {"path": "missing.md"},
        "File 'missing.md' not found",
    )
    assembler.observe(
        "semantic_search",
        {"query": "x"},
        "Semantic search failed: unavailable",
    )
    assembler.observe(
        "kb_grep",
        {"query": "x"},
        "No content matching 'x' in 'repo'",
    )
    assembler.observe(
        "kb_cat",
        {"path": "docs/secret.md"},
        "docs/secret.md (markdown, 1 lines)\n     1 | secret",
        succeeded=False,
    )
    assembler.observe(
        "kb_cat",
        "{malformed-json",
        "docs/secret.md (markdown, 1 lines)\n     1 | secret",
    )

    assert assembler.finalize("No sources.").citations == ()


def test_retrieval_and_search_results_preserve_source_metadata() -> None:
    assembler = FinalAnswerAssembler()
    assembler.observe(
        "knowledge_retrieve",
        '{"query": "revenue"}',
        json.dumps(
            {
                "chunks": [
                    {
                        "output_type": "text",
                        "content": "Retrieved 2 relevant documents",
                    },
                    {
                        "output_type": "markdown",
                        "content": "[1] Revenue grew 20%.\n[2] Margin reached 42%.",
                    },
                ]
            }
        ),
    )
    assembler.observe(
        "semantic_search",
        {"query": "auth"},
        "Semantic search 'auth' in docs:\n"
        "\n---\n### Result 1 (score: 0.91) [src/auth.py]\n"
        "Use a short-lived access token.\n"
        "\n---\n### Result 2 [docs/security.md]\n"
        "Rotate signing keys regularly.",
    )
    assembler.observe(
        "kb_grep",
        {"query": "timeout", "path": "src"},
        "'timeout' matched 1 files:\n\n"
        "src/client.py:\n"
        "  42: timeout = config.request_timeout",
    )

    citations = assembler.finalize("Answer.").to_dict()["citations"]

    assert [citation["index"] for citation in citations] == [1, 2, 3, 4, 5]
    assert citations[0]["sourceName"] == "Knowledge Base"
    assert citations[0]["excerpt"] == "Revenue grew 20%."
    assert citations[2]["sourceName"] == "src/auth.py"
    assert citations[2]["score"] == 0.91
    assert citations[3]["path"] == "docs/security.md"
    assert citations[4]["sourceName"] == "src/client.py"


def test_kb_grep_does_not_treat_a_matching_source_line_as_a_file_header() -> None:
    assembler = FinalAnswerAssembler()
    assembler.observe(
        "kb_grep",
        {"query": "timeout"},
        "'timeout' matched 1 files:\n\n"
        "src/client.py:\n"
        "  10: if timeout:\n"
        "  11: timeout = 30",
    )

    citations = assembler.finalize("Answer.").to_dict()["citations"]

    assert len(citations) == 1
    assert citations[0]["sourceName"] == "src/client.py"
    assert citations[0]["path"] == "src/client.py"
    assert citations[0]["excerpt"] == "10: if timeout:\n  11: timeout = 30"


def test_explicit_retrieval_citations_take_priority_over_legacy_chunks() -> None:
    assembler = FinalAnswerAssembler()
    assembler.observe(
        "knowledge_retrieve",
        {"query": "revenue"},
        json.dumps(
            {
                "citations": [
                    {
                        "id": "chunk-42",
                        "sourceName": "annual-report.md",
                        "chunkIndex": 1,
                        "score": 0.93,
                        "path": "reports/annual-report.md",
                        "url": "https://example.test/annual-report",
                    }
                ],
                "chunks": [
                    {
                        "output_type": "markdown",
                        "content": "[1] Revenue grew 20% year over year.",
                    }
                ],
            }
        ),
    )

    citations = assembler.finalize("Answer.").to_dict()["citations"]

    assert citations == [
        {
            "index": 1,
            "id": "chunk-42",
            "sourceName": "annual-report.md",
            "excerpt": "Revenue grew 20% year over year.",
            "score": 0.93,
            "path": "reports/annual-report.md",
            "url": "https://example.test/annual-report",
        }
    ]


def test_explicit_retrieval_citations_keep_sparse_chunk_numbers() -> None:
    assembler = FinalAnswerAssembler()
    assembler.observe(
        "knowledge_retrieve",
        {"query": "revenue"},
        json.dumps(
            {
                "citations": [
                    {
                        "id": "chunk-empty",
                        "sourceName": "empty.md",
                        "chunkIndex": 1,
                    },
                    {
                        "id": "chunk-real",
                        "sourceName": "annual-report.md",
                        "chunkIndex": 2,
                    },
                ],
                "chunks": [
                    {
                        "output_type": "markdown",
                        "content": "[1]   \n[2] Revenue grew 20% year over year.",
                    }
                ],
            }
        ),
    )

    citations = assembler.finalize("Answer.").to_dict()["citations"]

    assert citations == [
        {
            "index": 1,
            "id": "chunk-real",
            "sourceName": "annual-report.md",
            "excerpt": "Revenue grew 20% year over year.",
            "score": None,
            "path": None,
            "url": None,
        }
    ]


def test_non_finite_scores_are_not_serialized_into_sse_json() -> None:
    assembler = FinalAnswerAssembler()
    assembler.observe(
        "knowledge_retrieve",
        {"query": "revenue"},
        json.dumps(
            {
                "citations": [
                    {
                        "id": "chunk-nan",
                        "sourceName": "annual-report.md",
                        "excerpt": "Revenue data from the annual report.",
                        "score": "nan",
                    }
                ]
            }
        ),
    )

    payload = assembler.finalize("Answer.").to_sse_payload()

    assert payload["citations"][0]["score"] is None
    json.dumps(payload, allow_nan=False)


def test_citations_are_deduplicated_and_bounded() -> None:
    assembler = FinalAnswerAssembler()
    oversized = "x" * (MAX_CITATION_CHARS + 500)

    for number in range(MAX_CITATIONS + 5):
        body = oversized if number == 0 else f"supporting detail {number}"
        assembler.observe(
            "kb_cat",
            {"path": f"docs/{number}.md"},
            f"docs/{number}.md (markdown, 1 lines)\n     1 | {body}",
        )
    assembler.observe(
        "kb_cat",
        {"path": "docs/0.md"},
        f"docs/0.md (markdown, 1 lines)\n     1 | {oversized}",
    )

    citations = assembler.finalize("Answer.").citations

    assert len(citations) == MAX_CITATIONS
    assert all(len(citation.excerpt) <= MAX_CITATION_CHARS for citation in citations)
    assert sum(len(citation.excerpt) for citation in citations) <= (
        MAX_TOTAL_CITATION_CHARS
    )


def test_strip_only_a_trailing_legacy_references_block() -> None:
    legacy = (
        "Clean answer.\n\n"
        '<references title="References" references=\'[{"name":"KB"}]\'>'
        "</references>"
    )

    assert strip_legacy_references(legacy) == "Clean answer."
    assert strip_legacy_references("Keep <references> in an example.") == (
        "Keep <references> in an example."
    )
    assert (
        strip_legacy_references(
            "<references title=\"Example\" references='[]'></references>"
        )
        == "<references title=\"Example\" references='[]'></references>"
    )


def test_final_payload_never_embeds_legacy_reference_markup() -> None:
    assembler = FinalAnswerAssembler()
    content = (
        "Answer.\n\n"
        '<references title="References" references=\'[{"name":"KB"}]\'>'
        "</references>"
    )

    payload = assembler.finalize(content).to_sse_payload()

    assert payload["protocol_version"] == 2
    assert payload["content"] == "Answer."
    assert "<references" not in payload["content"]
