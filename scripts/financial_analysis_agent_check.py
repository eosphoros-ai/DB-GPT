"""Run the real conversational financial workflow and check persisted publication.

Uses the configured model and saves test conversations/files on the target server.
Run against an isolated test server, not a user's daily database.
"""

import argparse
import json
import time
from pathlib import Path
from uuid import uuid4

import httpx

BASE = "/api/v1/financial-analysis/runs"


def data(response):
    response.raise_for_status()
    body = response.json()
    assert body.get("success"), body.get("err_msg")
    return body["data"]


def chat(client, conversation, model, question, extra, output):
    events = []
    actions = []
    final = None
    try:
        with client.stream(
            "POST",
            "/api/v1/chat/react-agent",
            json={
                "conv_uid": conversation,
                "model_name": model,
                "chat_mode": "chat_react_agent",
                "user_input": question,
                "ext_info": dict(extra, skill_name="financial-report-analyzer"),
            },
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[5:])
                events.append(event)
                if event.get("type") == "step.meta" and event.get("action"):
                    action = event["action"]
                    actions.append(action)
                    print("ACTION", action, flush=True)
                if event.get("type") == "final":
                    final = event["content"]
    finally:
        output.write_text(
            json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    assert final and "{{" not in final, "Missing or unrendered final answer"
    return events, actions, final


def resume(output):
    events = json.loads(output.read_text(encoding="utf-8"))
    ref = next(
        e["content"]
        for e in reversed(events)
        if isinstance(e.get("content"), dict)
        and e["content"].get("kind") == "financial-report"
    )
    actions = [
        e["action"] for e in events if e.get("type") == "step.meta" and e.get("action")
    ]
    final = next(e["content"] for e in reversed(events) if e.get("type") == "final")
    return ref["sessionId"], events, actions, final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--pdf", type=Path, help="Defaults to the homepage PDF example")
    parser.add_argument("--model", default="qwen-plus")
    parser.add_argument("--user-id", default="financial-round10")
    parser.add_argument("--retry-topic", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse saved analysis; check follow-up only",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    conversation = "financial-agent-check-" + uuid4().hex
    started = time.monotonic()
    with httpx.Client(
        base_url=args.base_url,
        headers={"user-id": args.user_id},
        timeout=720,
    ) as client:
        if args.resume:
            conversation, events, actions, final = resume(
                args.output_dir / "analysis-events.json"
            )
        elif args.pdf:
            with args.pdf.open("rb") as stream:
                uploaded = data(
                    client.post(
                        "/api/v1/agent/files",
                        data={"session_id": conversation},
                        files={"files": (args.pdf.name, stream, "application/pdf")},
                    )
                )
            extra = {"session_id": conversation, "file_ids": [uploaded[0]["file_id"]]}
        else:
            extra = {
                "file_path": data(
                    client.post(
                        "/api/v1/examples/use", json={"example_id": "fin_report"}
                    )
                )
            }
        if not args.resume:
            events, actions, final = chat(
                client,
                conversation,
                args.model,
                "请分析这份年报，逐项完成财报专题分析、复核和发布，明确缺项与解释边界。",
                extra,
                args.output_dir / "analysis-events.json",
            )
        refs = [
            e["content"]
            for e in events
            if isinstance(e.get("content"), dict)
            and e["content"].get("kind") == "financial-report"
        ]
        assert refs, "No embedded report reference"
        ref = refs[-1]
        url = f"{BASE}/{ref['runId']}"
        params = {"session_id": conversation}
        report = data(client.get(url + "/report", params=params))
        (args.output_dir / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        assert report["workflow"]["status"] == "published", "Workflow stayed in draft"
        assert report["workflow"]["review"], "Missing explicit review"
        assert len(report["workflow"]["topics"]) == 6
        assert all(
            t["status"] in {"reviewed", "insufficient", "failed"}
            for t in report["workflow"]["topics"]
        )
        assert "prepare_financial_report" in actions
        assert {item["runId"] for item in refs} == {ref["runId"]}
        assert "publish_financial_report" in actions and actions[-1] == "terminate"
        history = data(
            client.get(
                "/api/v1/chat/dialogue/messages/history",
                params={"con_uid": conversation},
            )
        )
        assert ref["runId"] in json.dumps(history), (
            "Report reference not in chat history"
        )
        _, followup_actions, answer = chat(
            client,
            conversation,
            args.model,
            "本期营业收入是多少？请提供它的原文依据。",
            {},
            args.output_dir / "followup-events.json",
        )
        assert "read_financial_report" in followup_actions
        assert "prepare_financial_report" not in followup_actions
        revenue = next(
            f
            for f in report["facts"]
            if f["metricCode"] == "revenue"
            and f["fiscalPeriod"] == report["report"]["fiscalPeriod"]
        )
        assert revenue["displayValue"] in answer and "来源：原 PDF" in answer
        assert data(client.get(url + "/report", params=params)) == report
        if args.retry_topic:
            _, retry_actions, _ = chat(
                client,
                conversation,
                args.model,
                "只重新分析费用变化专题，保留其他专题，完成复核并发布新版本。",
                {},
                args.output_dir / "retry-events.json",
            )
            assert "get_financial_topic" in retry_actions
            assert "prepare_financial_report" not in retry_actions
            revised = data(client.get(url + "/report", params=params))
            assert revised["workflow"]["status"] == "published"
            assert revised["revision"] != report["revision"]
            assert (
                len(revised["workflow"]["history"])
                == len(report["workflow"]["history"]) + 1
            )
            assert [
                f
                for f in revised["findings"]
                if not f["id"].startswith("topic-expenses-")
            ] == [
                f
                for f in report["findings"]
                if not f["id"].startswith("topic-expenses-")
            ]
        result = {
            "conversation": conversation,
            "runId": ref["runId"],
            "analysisStatus": report["analysis"]["status"],
            "findingCount": len(report["findings"]),
            "topicStatuses": {
                t["id"]: t["status"] for t in report["workflow"]["topics"]
            },
            "actions": actions,
            "elapsedSeconds": round(time.monotonic() - started, 1),
            "final": final,
        }
        (args.output_dir / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            "PASS real agent publication, history and read-only follow-up", flush=True
        )


if __name__ == "__main__":
    main()
