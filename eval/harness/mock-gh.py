#!/usr/bin/env python3
"""Fail-closed, read-only GitHub CLI fixture for the skill pilot."""
import json
import os
import sys
from pathlib import Path

PROJECT = {"id": "PVT_EVAL", "number": 7, "title": "homelab", "url": "https://github.invalid/eval/homelab/projects/7", "closed": False}
FIELDS = [
    {"id": "F_STATUS", "name": "Status", "dataType": "SINGLE_SELECT", "options": [{"id": "O_TODO", "name": "Todo"}, {"id": "O_PROGRESS", "name": "In Progress"}, {"id": "O_DONE", "name": "Done"}]},
    {"id": "F_PRIORITY", "name": "Priority", "dataType": "SINGLE_SELECT", "options": [{"id": "O_HIGH", "name": "High"}, {"id": "O_MEDIUM", "name": "Medium"}]},
    {"id": "F_SIZE", "name": "Size", "dataType": "SINGLE_SELECT", "options": [{"id": "O_S", "name": "S"}, {"id": "O_M", "name": "M"}]},
]
ISSUES = [
    (418, "Upgrade backup verification", "OPEN", "Todo", "High", "M", "2026-07-10T12:00:00Z"),
    (420, "Document reverse proxy", "OPEN", "Todo", None, "S", "2026-08-03T12:00:00Z"),
    (430, "Fix flaky DNS checks", "OPEN", "In Progress", "Medium", None, "2026-09-04T12:00:00Z"),
    (437, "Investigate dashboard timeout", "OPEN", "Todo", None, None, "2026-08-21T12:00:00Z"),
    (440, "Rotate test certificates", "OPEN", None, "High", "S", "2026-09-11T12:00:00Z"),
    (401, "Retire old monitoring host", "CLOSED", "Done", "Medium", "M", "2026-08-01T12:00:00Z"),
]


def items():
    result = []
    for num, title, state, status, priority, size, updated in ISSUES:
        values = [{"name": value, "field": {"name": field}} for field, value in (("Status", status), ("Priority", priority), ("Size", size)) if value]
        result.append({"id": f"PVTI_{num}", "content": {"number": num, "title": title, "state": state, "url": f"https://github.invalid/eval/homelab/issues/{num}", "createdAt": "2026-06-01T12:00:00Z", "updatedAt": updated, "closedAt": updated if state == "CLOSED" else None, "labels": {"nodes": []}, "assignees": {"nodes": []}, "milestone": None}, "fieldValues": {"nodes": values}})
    return result


def main():
    argv = sys.argv[1:]
    body = {}
    if argv[:2] == ["api", "graphql"]:
        try:
            body = json.load(sys.stdin)
        except (ValueError, OSError):
            pass
    query = body.get("query", "")
    log = Path(os.environ.get("GH_MOCK_LOG", Path(__file__).resolve().parents[1] / "gh-calls.jsonl"))
    with log.open("a", encoding="utf-8") as out:
        out.write(json.dumps({"argv": argv, "operation": "mutation" if "mutation" in query.lower() else "read", "query": query[:160], "variables": body.get("variables", {})}) + "\n")
    if "mutation" in query.lower() or any(x in argv for x in ("edit", "create", "delete", "close", "add-item", "item-edit")):
        sys.exit("Mock refuses all GitHub writes")
    data = None
    if argv[:2] == ["api", "graphql"]:
        if "projectsV2(first: 10)" in query:
            data = {"repository": {"projectsV2": {"nodes": [PROJECT]}}}
        elif "projectV2(number:" in query:
            data = {"user": {"projectV2": PROJECT}}
        elif "projectsV2(first: 50)" in query:
            data = {"user": {"projectsV2": {"nodes": [PROJECT]}}}
        elif "fields(first: 50)" in query:
            data = {"node": {"fields": {"nodes": FIELDS}}}
        elif "items(first: 100" in query:
            data = {"node": {"items": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": items()}}}
        if data is not None:
            print(json.dumps({"data": data}))
            return
    elif argv[:2] == ["project", "list"]:
        data = {"projects": [PROJECT]}
    elif argv[:2] == ["project", "view"]:
        data = PROJECT
    elif argv[:2] == ["project", "item-list"]:
        data = {"items": [{"id": row["id"], "content": row["content"], "status": next((v for v in row["fieldValues"]["nodes"] if v["field"]["name"] == "Status"), None), "priority": next((v for v in row["fieldValues"]["nodes"] if v["field"]["name"] == "Priority"), None), "size": next((v for v in row["fieldValues"]["nodes"] if v["field"]["name"] == "Size"), None)} for row in items()]}
    elif argv[:2] == ["auth", "status"]:
        print("Mock GitHub CLI: fixture only; no live access")
        return
    if data is None:
        sys.exit("Mock refuses unsupported gh command (no live fallback): " + " ".join(argv))
    print(json.dumps(data))


if __name__ == "__main__":
    main()
