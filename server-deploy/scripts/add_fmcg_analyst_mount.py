#!/usr/bin/env python3
"""Добавить volume mount для fmcg-analyst в docker-compose.yml."""
from pathlib import Path

COMPOSE = Path("/home/algerd/dbgpt-deploy/docker-compose.yml")
MOUNT = "      - ./skills/fmcg-analyst:/app/skills/fmcg-analyst:ro\n"
ANCHOR = "      - ./skills/csv-data-analysis:/app/skills/csv-data-analysis:ro\n"

def main() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    if "fmcg-analyst" in text:
        print("fmcg-analyst mount already present")
        return
    if ANCHOR not in text:
        raise SystemExit("anchor not found in docker-compose.yml")
    text = text.replace(ANCHOR, ANCHOR + MOUNT, 1)
    COMPOSE.write_text(text, encoding="utf-8")
    print("added fmcg-analyst volume mount")


if __name__ == "__main__":
    main()
