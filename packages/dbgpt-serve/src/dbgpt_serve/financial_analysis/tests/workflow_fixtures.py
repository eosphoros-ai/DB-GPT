"""Pure synthetic workflow adapter, independent of persistence and Agent tools."""

import json

from dbgpt_serve.financial_analysis import workflow


class RecordingAnalyzer:
    """Deterministic SYNTHETIC model adapter; not a real semantic acceptance."""

    model = "synthetic-recovery-adapter"

    def __init__(self):
        self.calls = []

    def __call__(self, report, owner, session_id):
        topic_id = report["_activeTopic"]
        self.calls.append(topic_id)
        _, section, codes, _ = workflow.TOPICS[topic_id]
        entity = report["comparison"]["entities"][0]["id"]
        facts = [
            f
            for f in report["facts"]
            if f["entityId"] == entity
            and f["metricCode"] in codes
            and f.get("normalizedValue") is not None
        ]
        return json.dumps(
            {
                "findings": [
                    {
                        "section": section,
                        "title": "合成披露与解释限制",
                        "summary": "；".join("{{fact:" + f["id"] + "}}" for f in facts)
                        + "，需进一步核对附注。",
                        "supportStatus": "partial",
                        "factIds": [f["id"] for f in facts],
                        "calculationIds": [],
                        "evidenceExcerptIds": [],
                        "counterEvidence": [],
                        "unresolvedQuestions": ["仍待核对附注。"],
                        "entityIds": [entity],
                        "periods": sorted({f["fiscalPeriod"] for f in facts}),
                        "metricCodes": sorted({f["metricCode"] for f in facts}),
                        "subjectEntityId": entity,
                        "baselineEntityId": None,
                        "comparisonDirection": "none",
                    }
                ]
            },
            ensure_ascii=False,
        )

    def review(self, report, owner, session_id):
        return [
            {
                "topic_id": t["id"],
                "verdict": "pass"
                if t["status"] in {"ready", "reviewed"}
                else "insufficient",
                "directionChecked": True,
                "scopeChecked": True,
                "causalityChecked": True,
                "note": "合成适配器核对，仅用于流程测试，不是人工或模型验收。",
            }
            for t in report["workflow"]["topics"]
        ]
