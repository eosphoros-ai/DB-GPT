"""Deterministic assembly of executed artifacts into report blocks."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .report import (
    Artifact,
    ChartArtifact,
    ChartBlock,
    Claim,
    ClaimSegment,
    EvidenceReference,
    InsightBlock,
    MetricBlock,
    PythonArtifact,
    ReferenceArtifact,
    ReportBlock,
    ReportDocument,
    ReportPresentationBinding,
    ReportSection,
    SQLArtifact,
    TableBlock,
    TextBlock,
)
from .report_capture import select_artifact_result


class ReportAssembler:
    """Map captured artifacts to native blocks without inventing results."""

    def assemble(
        self,
        *,
        report_id: str,
        title: str,
        conv_uid: str,
        final_content: str,
        artifacts: Sequence[Artifact],
        supporting_artifact_ids: Iterable[str] = (),
        presentation_bindings: Sequence[
            ReportPresentationBinding | Dict[str, Any]
        ] = (),
        presentation: Optional[Dict[str, Any]] = None,
        include_artifact_detail_blocks: bool = False,
        include_chart_blocks: bool = False,
        created_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ReportDocument:
        """Build evidence sidecar data without replacing the rendered report."""
        content = final_content.strip()
        if not content:
            raise ValueError("final_content must not be blank")

        owned_artifacts = [artifact.model_copy(deep=True) for artifact in artifacts]
        artifact_by_id = {
            artifact.artifact_id: artifact for artifact in owned_artifacts
        }
        support_ids = [
            str(item) for item in supporting_artifact_ids if str(item).strip()
        ]
        summary_evidence = self._summary_evidence(artifact_by_id, support_ids)
        sections: List[ReportSection] = []
        # A final answer is not, by itself, report evidence. Keep it as task
        # metadata unless its caller supplied explicit, validated support.
        normalized_bindings = [
            item
            if isinstance(item, ReportPresentationBinding)
            else ReportPresentationBinding.model_validate(item)
            for item in presentation_bindings
        ]
        if summary_evidence and not normalized_bindings:
            sections.append(
                ReportSection(
                    section_id="summary",
                    title="核心结论",
                    blocks=[
                        InsightBlock(
                            block_id="summary-insight",
                            title="核心结论",
                            content=content,
                            evidence=summary_evidence,
                        )
                    ],
                )
            )
        presentation_blocks = self._presentation_blocks(
            normalized_bindings, artifact_by_id
        )
        if presentation_blocks:
            sections.append(
                ReportSection(
                    section_id="html-presentation",
                    title="分析报告",
                    blocks=presentation_blocks,
                )
            )
        # Execution artifacts belong to the evidence trail, not the user's report.
        # Keep this only for explicit audit/debug callers that need a tabular index.
        detail_blocks = (
            self._detail_blocks(owned_artifacts, artifact_by_id)
            if include_artifact_detail_blocks
            else []
        )
        if detail_blocks:
            sections.append(
                ReportSection(
                    section_id="analysis",
                    title="分析结果",
                    blocks=detail_blocks,
                )
            )
        elif include_chart_blocks:
            chart_blocks = self._chart_blocks(
                owned_artifacts,
                artifact_by_id,
                presentation_blocks,
            )
            if chart_blocks:
                sections.append(
                    ReportSection(
                        section_id="analysis-charts",
                        title="分析图表",
                        blocks=chart_blocks,
                    )
                )

        document_metadata = dict(metadata or {})
        document_metadata["task_summary"] = content
        if presentation:
            document_metadata["presentation"] = dict(presentation)
        document_metadata["assembly"] = {
            "version": 1,
            "artifact_count": len(owned_artifacts),
            "block_count": sum(len(section.blocks) for section in sections),
        }
        return ReportDocument(
            report_id=report_id,
            title=title,
            conv_uid=conv_uid,
            created_at=created_at or datetime.now(timezone.utc),
            sections=sections,
            artifacts=owned_artifacts,
            metadata=document_metadata,
        )

    def _presentation_blocks(
        self,
        bindings: Sequence[ReportPresentationBinding],
        artifact_by_id: Dict[str, Artifact],
    ) -> List[ReportBlock]:
        blocks: List[ReportBlock] = []
        for binding in bindings:
            evidence = self._binding_evidence(binding, artifact_by_id)
            if binding.target_type == "claim":
                text = binding.text or binding.label
                block_id = self._block_id("html-claim", binding.target_id)
                segment_id = self._block_id("segment", binding.target_id)
                target_evidence = [
                    item.model_copy(
                        update={
                            "target_selector": {
                                "kind": "text_segment",
                                "block_id": block_id,
                                "segment_id": segment_id,
                                "claim_id": binding.target_id,
                                "quote": text,
                            }
                        }
                    )
                    for item in evidence
                ]
                claim_type = self._claim_type(text)
                blocks.append(
                    InsightBlock(
                        block_id=block_id,
                        title=binding.label,
                        content=text,
                        segments=[
                            ClaimSegment(
                                segment_id=segment_id,
                                claim_id=binding.target_id,
                                text=text,
                            )
                        ],
                        claims=[
                            Claim(
                                claim_id=binding.target_id,
                                claim_type=claim_type,
                                text=text,
                            )
                        ],
                        evidence=target_evidence,
                        metadata={
                            "presentation_target": {
                                "kind": "html_claim",
                                "target_id": binding.target_id,
                            }
                        },
                    )
                )
            else:
                claim_type = self._claim_type(binding.label)
                is_evidence_inference = claim_type in {
                    "comparison",
                    "trend",
                    "ranking",
                    "aggregation",
                    "causal",
                    "recommendation",
                } and binding.element_tag not in {
                    "FIGURE",
                    "TABLE",
                    "IMG",
                    "SVG",
                    "CANVAS",
                }
                blocks.append(
                    TextBlock(
                        block_id=binding.target_id,
                        title=binding.label,
                        content=binding.label,
                        evidence=[
                            item.model_copy(
                                update={
                                    "target_selector": {
                                        "kind": "html_block",
                                        "block_id": binding.target_id,
                                    }
                                }
                            )
                            for item in evidence
                        ],
                        metadata={
                            "presentation_target": {
                                "kind": "html_block",
                                "target_id": binding.target_id,
                            },
                            "claim_type": claim_type,
                            "evidence_inference": is_evidence_inference,
                        },
                    )
                )
        return blocks

    @staticmethod
    def _binding_evidence(
        binding: ReportPresentationBinding,
        artifact_by_id: Dict[str, Artifact],
    ) -> List[EvidenceReference]:
        evidence: List[EvidenceReference] = []
        seen_artifact_ids: set[str] = set()

        def append_artifact(artifact_id: str) -> None:
            if artifact_id in seen_artifact_ids:
                return
            seen_artifact_ids.add(artifact_id)
            artifact = artifact_by_id.get(artifact_id)
            if artifact is None:
                raise ValueError(f"unknown presentation artifact {artifact_id}")
            if artifact.status != "succeeded":
                raise ValueError(
                    f"presentation artifact must have succeeded: {artifact_id}"
                )
            if isinstance(artifact, ReferenceArtifact):
                role = "source"
                selector = dict(artifact.locator) or {"kind": "reference"}
                citation = binding.artifact_selectors.get(artifact_id, {})
                quote = citation.get("quote") if isinstance(citation, dict) else None
                if isinstance(quote, str) and quote.strip():
                    selector["quoted_text"] = quote
            elif isinstance(artifact, ChartArtifact):
                role = "support"
                selector = {"kind": "chart"}
            else:
                role = "calculation"
                selector = {"kind": "result"}
                citation = binding.artifact_selectors.get(artifact_id, {})
                if (
                    "field" in citation
                    or "path" in citation
                    or citation.get("kind") == "sql"
                ):
                    try:
                        select_artifact_result(artifact, citation)
                    except (ValueError, TypeError) as error:
                        raise ValueError(
                            "REPORT_ATTRIBUTE_INVALID: "
                            "attribute=data-dbgpt-artifact-selectors; "
                            f"container={binding.target_id}; "
                            f"JSON path $.{artifact_id}; "
                            f"{error}"
                        ) from error
                    selector.update(citation)
                    if citation.get("kind") == "sql":
                        role = "source"
            evidence.append(
                EvidenceReference(
                    artifact_id=artifact_id,
                    role=role,
                    selector=selector,
                )
            )
            # Expand captured dependencies, including intermediate file snapshots.
            for input_artifact_id in artifact.input_artifact_ids:
                append_artifact(input_artifact_id)

        for artifact_id in binding.artifact_ids:
            append_artifact(artifact_id)
        return evidence

    def _summary_evidence(
        self,
        artifact_by_id: Dict[str, Artifact],
        supporting_artifact_ids: Sequence[str],
    ) -> List[EvidenceReference]:
        evidence = []
        seen = set()
        for artifact_id in supporting_artifact_ids:
            if artifact_id in seen:
                continue
            seen.add(artifact_id)
            artifact = artifact_by_id.get(artifact_id)
            if artifact is None:
                raise ValueError(f"unknown supporting artifact {artifact_id}")
            if artifact.status != "succeeded":
                raise ValueError(
                    f"supporting artifact must have succeeded: {artifact_id}"
                )
            if isinstance(artifact, ReferenceArtifact):
                role = "source"
                selector = dict(artifact.locator) or {"kind": "reference"}
            elif isinstance(artifact, (SQLArtifact, PythonArtifact)):
                role = "calculation"
                selector = {"kind": "result"}
            elif isinstance(artifact, ChartArtifact):
                role = "support"
                selector = {"kind": "chart"}
            else:
                continue
            evidence.append(
                EvidenceReference(
                    artifact_id=artifact.artifact_id,
                    role=role,
                    selector=selector,
                )
            )
        return evidence

    def _detail_blocks(
        self,
        artifacts: Sequence[Artifact],
        artifact_by_id: Dict[str, Artifact],
    ) -> List[ReportBlock]:
        blocks: List[ReportBlock] = []
        for artifact in artifacts:
            if artifact.status != "succeeded":
                continue
            if isinstance(artifact, (SQLArtifact, PythonArtifact)):
                tabular = self._tabular_result(artifact)
                if tabular is None:
                    continue
                columns, rows = tabular
                scalar = self._scalar_result(columns, rows)
                if scalar is not None:
                    column, value = scalar
                    blocks.append(
                        MetricBlock(
                            block_id=self._block_id("metric", artifact.artifact_id),
                            title=artifact.name or column,
                            value=value,
                            evidence=[
                                EvidenceReference(
                                    artifact_id=artifact.artifact_id,
                                    role="calculation",
                                    selector={
                                        "kind": "cell",
                                        "row": 0,
                                        "column": column,
                                    },
                                    target_selector={"field": "value"},
                                )
                            ],
                        )
                    )
                else:
                    blocks.append(
                        TableBlock(
                            block_id=self._block_id("table", artifact.artifact_id),
                            title=artifact.name or "Result table",
                            data_artifact_id=artifact.artifact_id,
                            evidence=[
                                EvidenceReference(
                                    artifact_id=artifact.artifact_id,
                                    role="calculation",
                                    selector={"kind": "result"},
                                )
                            ],
                        )
                    )
            elif isinstance(artifact, ChartArtifact):
                blocks.append(
                    ChartBlock(
                        block_id=self._block_id("chart", artifact.artifact_id),
                        title=artifact.name or artifact.chart_type,
                        chart_artifact_id=artifact.artifact_id,
                        evidence=self._chart_evidence(artifact, artifact_by_id),
                    )
                )
        return blocks

    @staticmethod
    def _claim_type(label: str) -> str:
        """Classify presentation claims without asking the model to self-score.

        HTML evidence bindings already provide the claim text, but do not carry a
        semantic type.  This deliberately small keyword classifier lets the
        confidence policy distinguish a directly measured value from a causal
        interpretation or recommendation.  Numeric claims remain metrics unless
        the language explicitly signals a higher-risk interpretation.
        """

        normalized = label.casefold()
        type_keywords = (
            (
                "recommendation",
                ("建议", "优先", "应当", "应该", "recommend", "should"),
            ),
            (
                "causal",
                ("原因", "由于", "导致", "驱动", "造成", "because", "cause"),
            ),
            (
                "ranking",
                ("排名", "居首", "第一", "top ", "top-", "rank"),
            ),
            (
                "comparison",
                ("高于", "低于", "最高", "最低", "相比", "compare", "higher", "lower"),
            ),
            (
                "trend",
                (
                    "趋势",
                    "上涨",
                    "下降",
                    "增长",
                    "下滑",
                    "环比",
                    "同比",
                    "trend",
                    "increase",
                    "decrease",
                ),
            ),
            ("aggregation", ("合计", "总计", "汇总", "total", "sum")),
        )
        for claim_type, keywords in type_keywords:
            if any(keyword in normalized for keyword in keywords):
                return claim_type
        if any(char.isdigit() for char in label):
            return "metric"
        return "descriptive"

    def _chart_blocks(
        self,
        artifacts: Sequence[Artifact],
        artifact_by_id: Dict[str, Artifact],
        presentation_blocks: Sequence[ReportBlock] = (),
    ) -> List[ReportBlock]:
        """Expose only executed charts in the main report, not every tool result.

        Native chart blocks are appended separately from the HTML presentation.
        A chart's execution lineage normally contains its SQL/Python inputs, while
        the KB formula/rule is deliberately attached to the matching HTML
        container. Preserve that local KB evidence on this derived chart block as
        well; otherwise the same visible chart has two different evidence drawers.
        """
        knowledge_by_chart_id: Dict[str, List[EvidenceReference]] = {}
        for block in presentation_blocks:
            evidence = getattr(block, "evidence", []) or []
            chart_ids = {
                item.artifact_id
                for item in evidence
                if isinstance(artifact_by_id.get(item.artifact_id), ChartArtifact)
            }
            references = [
                item
                for item in evidence
                if isinstance(artifact_by_id.get(item.artifact_id), ReferenceArtifact)
            ]
            for chart_id in chart_ids:
                target = knowledge_by_chart_id.setdefault(chart_id, [])
                known_ids = {item.artifact_id for item in target}
                target.extend(
                    item for item in references if item.artifact_id not in known_ids
                )

        def chart_evidence(chart: ChartArtifact) -> List[EvidenceReference]:
            evidence = self._chart_evidence(chart, artifact_by_id)
            known_ids = {item.artifact_id for item in evidence}
            for reference in knowledge_by_chart_id.get(chart.artifact_id, []):
                if reference.artifact_id not in known_ids:
                    evidence.append(reference)
                    known_ids.add(reference.artifact_id)
            return evidence

        # When HTML presentation bindings exist, only expose a native chart
        # that was explicitly selected by one of those bindings. Other chart
        # artifacts are exploratory tool output: putting them in the report
        # creates duplicate/uncontextualised charts and can detach them from
        # their metric-rule evidence. The no-presentation fallback preserves
        # the legacy behaviour for callers that request a chart-only report.
        selected_chart_ids = set(knowledge_by_chart_id)
        chart_artifacts = [
            artifact
            for artifact in artifacts
            if isinstance(artifact, ChartArtifact)
            and artifact.status == "succeeded"
            and (not presentation_blocks or artifact.artifact_id in selected_chart_ids)
        ]
        return [
            ChartBlock(
                block_id=self._block_id("chart", artifact.artifact_id),
                title=artifact.name or artifact.chart_type or "Chart",
                chart_artifact_id=artifact.artifact_id,
                evidence=chart_evidence(artifact),
            )
            for artifact in chart_artifacts
        ]

    @staticmethod
    def _tabular_result(
        artifact: SQLArtifact | PythonArtifact,
    ) -> Optional[Tuple[List[str], List[Any]]]:
        result = artifact.result
        inline = result.inline if result is not None else None
        if not isinstance(inline, dict):
            return None
        columns = inline.get("columns")
        rows = inline.get("rows")
        if not isinstance(columns, list) or not all(
            isinstance(column, str) for column in columns
        ):
            return None
        if not isinstance(rows, list):
            return None
        return columns, rows

    @staticmethod
    def _scalar_result(
        columns: List[str], rows: List[Any]
    ) -> Optional[Tuple[str, Any]]:
        if len(columns) != 1 or len(rows) != 1:
            return None
        row = rows[0]
        if isinstance(row, list) and len(row) == 1:
            return columns[0], row[0]
        if isinstance(row, dict) and set(row) == {columns[0]}:
            return columns[0], row[columns[0]]
        return None

    def _chart_evidence(
        self,
        chart: ChartArtifact,
        artifact_by_id: Dict[str, Artifact],
    ) -> List[EvidenceReference]:
        evidence = [
            EvidenceReference(
                artifact_id=chart.artifact_id,
                role="calculation",
                selector={"kind": "chart"},
            )
        ]
        visited = {chart.artifact_id}

        def append_inputs(artifact: Artifact) -> None:
            for input_id in artifact.input_artifact_ids:
                if input_id in visited:
                    continue
                visited.add(input_id)
                dependency = artifact_by_id.get(input_id)
                if dependency is None:
                    continue
                is_reference = isinstance(dependency, ReferenceArtifact)
                role = "source" if is_reference else "calculation"
                selector = (
                    dict(dependency.locator) or {"kind": "reference"}
                    if is_reference
                    else {"kind": "result"}
                )
                evidence.append(
                    EvidenceReference(
                        artifact_id=input_id,
                        role=role,
                        selector=selector,
                    )
                )
                append_inputs(dependency)

        append_inputs(chart)
        return evidence

    @staticmethod
    def _block_id(prefix: str, artifact_id: str) -> str:
        token = hashlib.sha256(artifact_id.encode("utf-8")).hexdigest()[:20]
        return f"{prefix}-{token}"


__all__ = ["ReportAssembler"]
