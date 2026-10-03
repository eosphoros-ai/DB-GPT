"""Verify real template generation; retain each attempt and enforce a two-run cap.

Run with the repository packages on PYTHONPATH. This creates saved sample boards
in the selected local environment; it does not invoke a model or edit source data.
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import requests
from dbgpt_app.openapi.api_v1.dashboard.catalog import TEMPLATES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--environment", choices=["candidate", "formal"], default="candidate"
    )
    parser.add_argument(
        "--evidence-root",
        default="docs/dashboard/evidence/v9-4-template-workspace-20260908",
    )
    parser.add_argument("--template", action="append", default=[])
    args = parser.parse_args()
    unknown = set(args.template) - {template["id"] for template in TEMPLATES}
    if unknown:
        parser.error("Unknown template IDs: " + ", ".join(sorted(unknown)))
    base = f"http://127.0.0.1:{5671 if args.environment == 'formal' else 5672}/api/v1"
    evidence = Path(args.evidence_root).resolve()
    admitted, failed = [], []
    for template in TEMPLATES:
        if args.template and template["id"] not in args.template:
            continue
        directory = evidence / "templates" / template["id"]
        directory.mkdir(parents=True, exist_ok=True)
        existing = [
            json.loads(p.read_text(encoding="utf-8"))
            for p in directory.glob("attempt-*/admission.json")
        ]
        matched = next(
            (
                p
                for p in existing
                if p.get("environment", "").split(" ", 1)[0] == args.environment
            ),
            None,
        )
        if matched:
            admitted.append(matched)
            continue
        attempts = list(directory.glob("attempt-*/request.json"))
        if len(attempts) >= 2:
            failed.append({"id": template["id"], "reason": "two-attempt cap"})
            continue
        attempt = directory / f"attempt-{len(attempts) + 1}"
        attempt.mkdir(exist_ok=False)

        def save(name, value):
            (attempt / name).write_text(
                json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        body = {"data_source_id": template["source"]}
        save(
            "request.json",
            {"environment": args.environment, "base": base, "body": body},
        )
        start = time.monotonic()
        try:
            info = requests.get(
                base + f"/dashboard-catalog/{template['id']}/source",
                params=body,
                timeout=30,
            )
            save("source.json", info.json())
            info.raise_for_status()
            response = requests.post(
                base + f"/dashboard-catalog/{template['id']}/generate",
                json=body,
                timeout=180,
            )
            save("response.json", response.json())
            response.raise_for_status()
            payload = response.json()
            assert payload["success"], payload
            record = payload["data"]
            board = record["id"]
            reopened = requests.get(base + "/dashboards/" + board, timeout=30).json()[
                "data"
            ]
            assert (
                reopened["schema"] == record["schema"]
                and reopened["asset_state"] == "saved"
            )
            save("reopened.json", reopened)
            filters = record["schema"]["filters"]
            results = {}
            for label, values in [
                ("default", {}),
                ("year", {"year": filters[0]["options"][-1]["value"]}),
                ("segment", {"segment": filters[1]["options"][1]["value"]}),
            ]:
                response = requests.post(
                    base + "/dashboards/" + board + "/refresh",
                    json={"filters": values},
                    timeout=120,
                )
                save(label + "-snapshot.json", response.json())
                response.raise_for_status()
                snap = response.json()["data"]
                assert all(not w.get("error") for w in snap["widgets"].values()), snap
                if label == "default":
                    assert all(
                        w["row_count"] > 0 for w in snap["widgets"].values()
                    ), snap
                results[label] = {
                    key: w["rows"][0] if w["rows"] else []
                    for key, w in snap["widgets"].items()
                }
            assert (
                results["default"] != results["year"]
                and results["default"] != results["segment"]
            )
            proof = {
                "id": template["id"],
                "source": template["source"],
                "dashboardId": board,
                "revision": record["current_revision"],
                "environment": args.environment,
                "duration_seconds": round(time.monotonic() - start, 2),
                "verified_at": datetime.now().isoformat(),
                "generator": "validated-source-mapping-and-fixed-layout",
                "steps": [
                    "connect",
                    "generate",
                    "save",
                    "reopen",
                    "filter-year",
                    "filter-segment",
                ],
                "live_model_calls": 0,
                "results": results,
            }
            save("admission.json", proof)
            admitted.append(proof)
            print("PASS", template["id"], board, proof["duration_seconds"], flush=True)
        except Exception as error:
            failure = {
                "id": template["id"],
                "error": str(error),
                "elapsed_seconds": round(time.monotonic() - start, 2),
            }
            save("failure.json", failure)
            failed.append(failure)
            print("FAIL", template["id"], str(error)[:500], flush=True)
    summary = {
        "environment": args.environment,
        "passed": len(admitted),
        "failed": failed,
        "admitted": admitted,
        "attempt_cap": 2,
    }
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (evidence / f"template-{args.environment}-{stamp}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
