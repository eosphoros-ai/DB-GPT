"""Check saved history and real exports; optionally analyze one public PDF."""

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from uuid import uuid4

import httpx

BASE = "/api/v1/financial-analysis/runs"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--user-id", default="001")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(
        base_url=args.base_url, headers={"user-id": args.user_id}, timeout=180
    ) as client:
        def data(response):
            response.raise_for_status()
            return response.json()["data"]

        if args.pdf:
            session_id = "lifecycle-" + uuid4().hex
            uploaded = data(
                client.post(
                    "/api/v1/agent/files",
                    data={"session_id": session_id},
                    files={
                        "files": (
                            args.pdf.name,
                            args.pdf.read_bytes(),
                            "application/pdf",
                        )
                    },
                )
            )
            run = data(
                client.post(
                    BASE,
                    json={
                        "session_id": session_id,
                        "file_ids": [uploaded[0]["file_id"]],
                        "request_id": str(uuid4()),
                    },
                )
            )
            (args.output_dir / "new-run.json").write_text(
                json.dumps(run, indent=2), encoding="utf-8"
            )
            started = time.monotonic()
            while True:
                run = data(
                    client.get(
                        f"{BASE}/{run['id']}", params={"session_id": session_id}
                    )
                )
                if run["status"] == "failed" or (
                    run["status"] == "completed"
                    and run.get("analysis_status") != "running"
                ):
                    break
                assert time.monotonic() - started < 300, "Run timed out"
                time.sleep(1)
            assert run["status"] == "completed", run
        history = data(client.get(BASE, params={"page_size": 30}))
        records = []
        checked_documents = set()
        for run in [r for r in history["items"] if r["report_ready"]]:
            url = f"{BASE}/{run['id']}"
            params = {"session_id": run["session_id"]}
            report = data(client.get(url + "/report", params=params))
            if report.get("analysis", {}).get("status") == "running":
                continue
            digest = report["documents"][0]["sha256"]
            if digest in checked_documents:
                continue
            checked_documents.add(digest)
            (args.output_dir / f"{run['id']}-report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            exports = []
            for kind in ["json", "html"]:
                body = dict(params, revision=report["revision"], format=kind)
                export = data(client.post(url + "/exports", json=body))
                assert data(client.post(url + "/exports", json=body)) == export
                downloaded = client.get(
                    url + "/exports/" + export["id"], params=params
                )
                downloaded.raise_for_status()
                assert len(downloaded.content) == export["size_bytes"]
                assert (
                    hashlib.sha256(downloaded.content).hexdigest()
                    == export["sha256"]
                )
                if kind == "json":
                    assert downloaded.json() == report
                else:
                    embedded = re.search(
                        r'id="financial-report-data">(.*?)</script>',
                        downloaded.text,
                        re.S,
                    )
                    assert embedded and json.loads(embedded.group(1)) == report
                    assert "<!--FINANCIAL_REPORT_JSON-->" not in downloaded.text
                (args.output_dir / export["file_name"]).write_bytes(
                    downloaded.content
                )
                exports.append(export)
            listing = data(client.get(url + "/exports", params=params))
            assert {e["id"] for e in exports} <= {e["id"] for e in listing}
            assert data(client.get(url + "/report", params=params)) == report
            assert (
                client.get(
                    url + "/exports", headers={"user-id": "other"}, params=params
                ).status_code
                == 404
            )
            records.append(dict(run=run, exports=exports))
            print(
                f"PASS {run['id']}: reopen, revision, JSON/HTML, "
                "digest, idempotency and owner isolation",
                flush=True,
            )
            if len(records) == 3:
                break
        assert records, "No completed reports were checked"
        (args.output_dir / "lifecycle-check.json").write_text(
            json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
