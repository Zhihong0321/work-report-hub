#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Push a work report to the hosted Work Report Hub.")
    parser.add_argument("--app-url", required=True, help="Base URL of the hosted app.")
    parser.add_argument("--api-key", required=True, help="APP_API_KEY configured on the app.")
    parser.add_argument("--project-name", required=True, help="Display name for the project.")
    parser.add_argument("--repo-name", required=True, help="Repository or GitHub name.")
    parser.add_argument("--title", required=True, help="Short completed-work title.")
    parser.add_argument("--report-date", help="Date in YYYY-MM-DD format.")
    parser.add_argument("--source", default="codex", help="Optional source label.")

    detail_group = parser.add_mutually_exclusive_group(required=True)
    detail_group.add_argument("--detail", help="Full detail text.")
    detail_group.add_argument("--detail-file", help="Path to a text or markdown file for the detail body.")

    return parser.parse_args()


def load_detail(args: argparse.Namespace) -> str:
    if args.detail:
        return args.detail.strip()
    return Path(args.detail_file).read_text(encoding="utf-8").strip()


def main() -> int:
    args = parse_args()
    payload = {
        "project_name": args.project_name.strip(),
        "repo_name": args.repo_name.strip(),
        "title": args.title.strip(),
        "detail": load_detail(args),
        "source": args.source.strip() or "codex",
    }
    if args.report_date:
        payload["report_date"] = args.report_date.strip()

    request = urllib.request.Request(
        url=args.app_url.rstrip("/") + "/api/reports",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-API-Key": args.api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        print(message, file=sys.stderr)
        return exc.code or 1
    except urllib.error.URLError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    report = body.get("report", {})
    print(f"Stored report {report.get('id')} for {report.get('repo_name')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
