"""Check maintained docs, portable paths and regression inputs without a server."""

import argparse
import ast
import csv
import hashlib
import json
import re
import subprocess
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "web/tests/dashboard-e2e/fixtures"
UPLOAD = ROOT / "scripts/acceptance/fixtures/upload-samples"
LINK = re.compile(r"!?\[[^\]]*\]\((<[^>]+>|[^)\n]+)\)")


def repository_files():
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return {
        name
        for name in result.stdout.decode("utf-8").split("\0")
        if name and (ROOT / name).is_file()
    }


def markdown_links(path):
    text = path.read_text(encoding="utf-8-sig")
    text = re.sub(r"^```[^\n]*\n.*?^```[^\n]*$", "", text, flags=re.M | re.S)
    for match in LINK.finditer(text):
        target = match[1].strip().strip("<>")
        if re.match(r"^[a-zA-Z][a-zA-Z+.-]*:", target):
            continue
        target = unquote(target.split("#", 1)[0].split("?", 1)[0])
        if not target:
            continue
        resolved = (
            ROOT / target.lstrip("/")
            if target.startswith("/")
            else path.parent / target
        ).resolve()
        yield target, resolved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="Optional local result file")
    args = parser.parse_args()
    errors = []
    counts = {}
    available = repository_files()
    dirs = {str(Path(p).parent).replace("\\", "/") for p in available}
    for name in list(dirs):
        dirs.update(parent.as_posix() for parent in Path(name).parents)

    docs = sorted((ROOT / "docs/dashboard").rglob("*.md"))
    docs += [
        ROOT / "DASHBOARD_PROJECT.md",
        FIXTURES / "README.md",
        UPLOAD / "README.md",
    ]
    links = 0
    for path in docs:
        for target, resolved in markdown_links(path):
            links += 1
            try:
                name = resolved.relative_to(ROOT).as_posix()
            except ValueError:
                name = None
            if name not in available and name not in dirs:
                errors.append(
                    f"Unavailable repository link: {path.relative_to(ROOT)} -> {target}"
                )
    counts.update(markdown_files=len(docs), local_links=links)

    for directory, label in ((FIXTURES, "browser"), (UPLOAD, "upload")):
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        listed = set()
        for entry in manifest["fixtures"]:
            path = (directory / entry["path"]).resolve()
            if not path.is_relative_to(directory) or not path.is_file():
                errors.append(f"Invalid {label} fixture path: {entry['path']}")
                continue
            listed.add(path.relative_to(directory).as_posix())
            if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                errors.append(f"Changed {label} fixture hash: {entry['path']}")
            if path.suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))
            text = path.read_text(encoding="utf-8-sig")
            if re.search(r"(?<![A-Za-z])(?:[A-Za-z]:[\\/]|/(?:Users|home)/)", text):
                errors.append(
                    f"Private absolute path in {label} fixture: {entry['path']}"
                )
            if re.search(
                r'"(?:api_key|access_token|refresh_token|password|private_key)"\s*:\s*"[^"\s]+"',
                text,
                flags=re.I,
            ):
                errors.append(f"Credential field in {label} fixture: {entry['path']}")
        actual = {
            path.relative_to(directory).as_posix()
            for path in directory.rglob("*")
            if path.is_file() and path.name not in {"manifest.json", "README.md"}
        }
        if listed != actual:
            errors.append(
                f"{label} manifest coverage mismatch: {sorted(listed ^ actual)}"
            )
        counts[label + "_fixtures"] = len(listed)

    def rows(name):
        with (UPLOAD / name).open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))

    customers, orders, items = (
        rows("customers.csv"),
        rows("orders.csv"),
        rows("order_items.csv"),
    )
    customer_map = {row["customer_id"]: row for row in customers}
    order_map = {row["order_id"]: row for row in orders}
    if len(customer_map) != len(customers) or len(order_map) != len(orders):
        errors.append("Duplicate customer/order keys in upload samples")
    if len({(row["order_id"], row["line_no"]) for row in items}) != len(items):
        errors.append("Duplicate order line keys in upload samples")
    monthly, regional = defaultdict(Decimal), defaultdict(Decimal)
    for order in orders:
        if order["customer_id"] not in customer_map:
            errors.append("An order references an unknown customer")
    for row in items:
        order = order_map.get(row["order_id"])
        customer = customer_map.get(order["customer_id"]) if order else None
        if not order or not customer:
            errors.append("Broken upload sample relationship")
            continue
        amount = Decimal(row["quantity"]) * Decimal(row["unit_price"])
        monthly[order["order_date"][:7]] += amount
        regional[customer["region"]] += amount
    if dict(monthly) != {"2024-01": 250, "2024-02": 1100, "2024-03": 150}:
        errors.append("Upload sample monthly amounts differ from the business contract")
    if dict(regional) != {"华东": 350, "华南": 1000, "华北": 150}:
        errors.append(
            "Upload sample regional amounts differ from the business contract"
        )
    if sum(monthly.values()) != 1500 or (len(customers), len(orders), len(items)) != (
        3,
        4,
        5,
    ):
        errors.append("Upload sample total or row counts changed")
    counts["upload_join_total"] = str(sum(monthly.values()))

    reference = json.loads(
        (ROOT / "data/dashboard_reference_sources/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    for entry in reference:
        name = entry["database"]
        if (
            re.match(r"^[A-Za-z]:", name)
            or Path(name).is_absolute()
            or ".." in Path(name).parts
        ):
            errors.append(f"Nonportable reference database path: {entry['name']}")
        elif name not in available:
            errors.append(f"Reference database not included: {entry['name']}")
    counts["relative_database_paths"] = len(reference)

    for name in ("install_reference_sources.py", "verify_pr_materials.py"):
        path = ROOT / "scripts/dashboard" / name
        ast.parse(path.read_text(encoding="utf-8"), filename=name)
    result = {"success": not errors, "checks": counts, "errors": errors}
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
