"""Isolated comparison acceptance; never loads the daily application database.

uv run --no-sync python scripts/verify_financial_comparison.py --output-dir <temp>
Add --real-pdfs <a.pdf> <b.pdf> to exercise actual extraction/storage.
Add --model-config <toml> --env-file .env for an explicitly selected model run.
All fixtures are marked synthetic; model and real-PDF results are kept separate.
"""

import argparse
import hashlib
import json
import sys
import tempfile
import time
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dbgpt_serve.financial_analysis import workflow
from dbgpt_serve.financial_analysis.analysis import SYSTEM_PROMPT, model_context
from dbgpt_serve.financial_analysis.comparison_analysis import (
    COMPARISON_INSTRUCTIONS,
    review_context,
)
from dbgpt_serve.financial_analysis.exports import render_export
from dbgpt_serve.financial_analysis.report import build_report
from dbgpt_serve.financial_analysis.service import FinancialAnalysisService
from dbgpt_serve.financial_analysis.tests.fixtures import extracted, report_config
from dbgpt_serve.financial_analysis.tests.test_comparison_analysis import (
    comparison_report,
)

ROOT = Path(__file__).resolve().parents[1]


def write_snapshot(directory, name, report, runtime, *, language="zh"):
    (directory / (name + ".json")).write_text(
        render_export(report, "json"), encoding="utf-8"
    )
    if runtime:
        (directory / (name + ".html")).write_text(
            render_export(report, "html", runtime, language=language), encoding="utf-8"
        )


def synthetic_snapshots(directory, runtime):
    base = comparison_report()
    base["synthetic"] = True
    base["comparison"]["title"] = "合成甲与合成乙 · 测试 fixture"
    for name in (
        "normal",
        "missing",
        "conflict",
        "incomparable",
        "file-failure",
        "analyzing",
        "published",
    ):
        report = deepcopy(base)
        revenue = next(
            c for c in report["comparison"]["cells"] if c["metricCode"] == "revenue"
        )
        if name in {"missing", "conflict"}:
            revenue.update(
                factId=None,
                dataStatus=name,
                selectionReason=(
                    "missing_input"
                    if name == "missing"
                    else "unexplained_conflicting_values"
                ),
            )
            if name == "missing":
                revenue["candidateFactIds"] = []
        if name == "incomparable":
            revenue["comparability"] = {
                "status": "incomparable",
                "rules": ["scope"],
                "reasons": ["incompatible_basis"],
            }
        if name == "file-failure":
            report["members"].append(
                {
                    "file_id": "failed",
                    "file_name": "synthetic-failed.pdf",
                    "status": "failed",
                    "error": "合成的文件提取失败",
                    "sha256": "f" * 64,
                    "extractor_version": "financial-document-v2",
                }
            )
        if name == "analyzing":
            report["analysis"]["status"] = "running"
        if name == "published":
            for topic in report["workflow"]["topics"]:
                topic["status"] = "insufficient"
            report["workflow"]["review"] = {
                "at": "2026-10-24",
                "items": [],
                "kind": "agent-review",
            }
            report = workflow.publish(report)
        write_snapshot(directory, name, report, runtime)
        if name == "published":
            write_snapshot(directory, "published-en", report, runtime, language="en")
    single = build_report(
        extracted(),
        {"id": str(uuid4()), "completed_at": "2026-10-24T00:00:00+00:00"},
        SimpleNamespace(display_name="synthetic.pdf", file_id="single", size_bytes=20),
    )
    single["synthetic"] = True
    write_snapshot(directory, "single", single, runtime)


class ConfiguredAnalyzer:
    """Acceptance-only adapter to the explicitly selected compatible endpoint."""

    def __init__(self, config_path, env_path):
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib

        from dotenv import dotenv_values

        settings = tomllib.loads(Path(config_path).read_text(encoding="utf-8"))
        llm = settings["models"]["llms"][0]
        environment = dotenv_values(env_path)
        credential = llm["api_key"]
        if credential.startswith("${env:") and credential.endswith("}"):
            credential = environment.get(credential[6:-1])
        if not credential:
            raise ValueError("Selected model credential is unavailable")
        self.key = credential
        self.url = llm["api_base"].rstrip("/") + "/chat/completions"
        self.model = llm["name"]
        self.calls = 0

    def generate(self, prompt, context):
        import httpx

        self.calls += 1
        response = httpx.post(
            self.url,
            headers={"Authorization": "Bearer " + self.key},
            json={
                "model": self.model,
                "temperature": 0,
                "max_tokens": 4000,
                "messages": [
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": json.dumps(context, ensure_ascii=False),
                    },
                ],
            },
            timeout=100,
        )
        if response.status_code != 200:
            # Never include the URL, request headers or provider error body.
            raise ValueError("Model response status " + str(response.status_code))
        text = response.json()["choices"][0]["message"]["content"].strip()
        if text.startswith("```json") and text.endswith("```"):
            text = text[7:-3].strip()
        return text

    def __call__(self, report, owner, session_id):
        topic = report.get("_activeTopic")
        print("MODEL_TOPIC", topic or "report", flush=True)
        context = (
            workflow.topic_context(report, topic) if topic else model_context(report)
        )
        return self.generate(SYSTEM_PROMPT + COMPARISON_INSTRUCTIONS, context)

    def review(self, report, owner, session_id):
        print("MODEL_REVIEW", flush=True)
        return json.loads(
            self.generate(
                "你是财报复核助手，严格按输入复核要求只输出JSON。",
                review_context(report),
            )
        )["reviews"]


def real_acceptance(
    directory,
    pdfs,
    runtime,
    analyzer=None,
    resume_database=None,
    resume_run_id=None,
    review_only=False,
):
    files = {str(i): Path(path).resolve() for i, path in enumerate(pdfs)}
    database = (
        Path(resume_database).resolve()
        if resume_database
        else directory / ("acceptance-" + uuid4().hex + ".sqlite")
    )
    if resume_database and (
        database.parent != directory
        or not database.name.startswith("acceptance-")
        or database.suffix != ".sqlite"
        or not database.is_file()
        or not resume_run_id
    ):
        raise ValueError("Resume requires an existing isolated acceptance DB and run")
    engine = create_engine(
        "sqlite:///" + database.as_posix(), connect_args={"check_same_thread": False}
    )
    factory = sessionmaker(bind=engine)

    @contextmanager
    def session(commit=True):
        with factory() as db_session:
            yield db_session
            if commit:
                db_session.commit()

    records = {
        key: SimpleNamespace(
            file_id=key,
            display_name=path.name,
            size_bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            media_type="application/pdf",
        )
        for key, path in files.items()
    }

    def get_file(*, owner_id, session_id, file_id):
        return (
            records.get(file_id)
            if (owner_id, session_id) == ("acceptance", "isolated")
            else None
        )

    def open_download(**kwargs):
        record = get_file(**kwargs)
        if record:
            return files[record.file_id].open("rb"), record

    @contextmanager
    def materialize(scope, stream, suffix):
        with tempfile.TemporaryDirectory(prefix="document-", dir=directory) as temp:
            path = Path(temp) / ("report" + suffix)
            with path.open("wb") as output:
                while chunk := stream.read(1024 * 1024):
                    output.write(chunk)
            yield path

    extraction_calls = []

    def extract(path):
        sys.path.insert(0, str(ROOT / "skills/financial-report-analyzer/scripts"))
        from financial_document import extract_document

        started = time.monotonic()
        result = extract_document(path)
        elapsed = round(time.monotonic() - started, 3)
        extraction_calls.append(
            {"sha256": result["document"]["sha256"], "seconds": elapsed}
        )
        (directory / (result["document"]["sha256"] + ".extracted.json")).write_text(
            json.dumps(result, ensure_ascii=False), encoding="utf-8"
        )
        print("EXTRACTED", result["company_name"], elapsed, flush=True)
        return result

    service = FinancialAnalysisService(
        SimpleNamespace(
            dao=SimpleNamespace(session=session),
            get_file=get_file,
            open_download=open_download,
            materialize_local_file=materialize,
        ),
        extractor=extract,
        analyzer=analyzer,
        export_runtime=runtime,
    )
    run_id = resume_run_id or str(uuid4())
    total_started = time.monotonic()
    try:
        if resume_database:
            existing = service.get("acceptance", "isolated", run_id, report=True)
            if review_only:
                if not analyzer or any(
                    t["status"] not in workflow.TERMINAL
                    for t in existing["workflow"]["topics"]
                ):
                    raise ValueError("Review requires a model and terminal topics")
                service.comparisons.analyze("acceptance", "isolated", run_id, existing)
            else:
                service.comparisons.resume(
                    "acceptance", "isolated", run_id, existing["revision"]
                )
        else:
            if review_only:
                raise ValueError("Review-only requires an existing isolated run")
            service.comparisons.create(
                "acceptance",
                "isolated",
                list(files),
                run_id,
                report_config(baseline="0"),
            )
        while True:
            if time.monotonic() - total_started > 1600:
                raise TimeoutError("Acceptance exceeded bounded deadline")
            state = service.get("acceptance", "isolated", run_id)
            if (
                state["status"] not in {"pending", "running"}
                and state["stage"] != "agent_topics"
            ):
                if (
                    analyzer
                    and state.get("report_ready")
                    and state["stage"] == "data_ready"
                    and state.get("lifecycle", {}).get("dataStatus") == "ready"
                ):
                    # Data-ready is committed before the worker enters model work.
                    time.sleep(0.1)
                    continue
                break
            time.sleep(0.2)
        report = service.get("acceptance", "isolated", run_id, report=True)
        write_snapshot(directory, "real-peer", report, runtime)
        before_calls = len(extraction_calls)
        service.latest_agent_report("acceptance", "isolated")
        service.get(
            "acceptance", "isolated", run_id, report=True, revision=report["revision"]
        )
        assert len(extraction_calls) == before_calls
        summary = {
            "synthetic": False,
            "resumed": bool(resume_database),
            "reviewOnly": review_only,
            "run_id": run_id,
            "database": str(database),
            "files": [
                {
                    "path": str(files[key]),
                    "sha256": record.sha256,
                    "sizeBytes": record.size_bytes,
                }
                for key, record in records.items()
            ],
            "extractions": extraction_calls,
            "modelCalls": analyzer.calls if analyzer else 0,
            "totalSeconds": round(time.monotonic() - total_started, 3),
            "timings": report.get("timings"),
            "lifecycle": report["lifecycle"],
            "comparisonReady": report["comparison"]["ready"],
            "findings": len(report["findings"]),
            "topicStatuses": {
                t["id"]: t["status"] for t in report["workflow"]["topics"]
            },
            "reviewIssues": report.get("analysis", {}).get("reviewIssues", []),
            "revision": report["revision"],
            "humanVerified": False,
            "unverified": [
                "Independent human gold values",
                "Same company different annual PDFs",
                "Real restatement/conflict materials",
            ],
        }
        (directory / "real-acceptance.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        with (directory / "real-acceptance-attempts.jsonl").open(
            "a", encoding="utf-8"
        ) as output:
            output.write(json.dumps(summary, ensure_ascii=False) + "\n")
        print(json.dumps(summary, ensure_ascii=False), flush=True)
    finally:
        service.close()
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--runtime")
    parser.add_argument("--real-pdfs", nargs="+")
    parser.add_argument("--model-config")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--resume-database")
    parser.add_argument("--resume-run-id")
    parser.add_argument("--review-only", action="store_true")
    args = parser.parse_args()
    if not args.real_pdfs and (
        args.resume_database is not None
        or args.resume_run_id is not None
        or args.review_only
        or args.model_config is not None
    ):
        parser.error(
            "--resume-database, --resume-run-id, --review-only and --model-config "
            "require --real-pdfs"
        )
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    synthetic_snapshots(output, args.runtime)
    if args.real_pdfs:
        analyzer = (
            ConfiguredAnalyzer(args.model_config, args.env_file)
            if args.model_config
            else None
        )
        real_acceptance(
            output,
            args.real_pdfs,
            args.runtime,
            analyzer,
            args.resume_database,
            args.resume_run_id,
            args.review_only,
        )


if __name__ == "__main__":
    main()
