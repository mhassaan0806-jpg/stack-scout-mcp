"""Search GitHub for repositories that provide a building block (auth, payments, ...).

Uses the free GitHub REST API. Works without a token (10 searches/min);
set GITHUB_TOKEN in .env to raise that to 30/min.

CLI:
    python tools/github_search.py "headless cms" --language TypeScript --limit 10
    python tools/github_search.py --repo medusajs/medusa
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # allow `python tools/x.py`
from tools._common import http_get, load_env  # noqa: E402

API = "https://api.github.com"


def _headers() -> dict:
    load_env()
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def slim_repo(r: dict) -> dict:
    """Keep only the fields the rest of the pipeline uses."""
    lic = r.get("license") or {}
    return {
        "full_name": r["full_name"],
        "url": r["html_url"],
        "description": (r.get("description") or "").strip(),
        "stars": r.get("stargazers_count", 0),
        "forks": r.get("forks_count", 0),
        "open_issues": r.get("open_issues_count", 0),
        "language": r.get("language"),
        "license": lic.get("spdx_id") or None,
        "license_name": lic.get("name"),
        "pushed_at": r.get("pushed_at"),
        "archived": bool(r.get("archived")),
        "fork": bool(r.get("fork")),
        "topics": r.get("topics") or [],
        "homepage": r.get("homepage") or None,
    }


def search_repos(query: str, language: str | None = None, min_stars: int = 50, limit: int = 15) -> list[dict]:
    """Return up to `limit` repos for `query`, in GitHub's best-match order."""
    parts = [query.strip(), "archived:false", "fork:false", f"stars:>={min_stars}"]
    if language:
        parts.append(f'language:"{language}"')
    params = urllib.parse.urlencode({"q": " ".join(parts), "per_page": max(1, min(limit, 50))})
    data = json.loads(http_get(f"{API}/search/repositories?{params}", headers=_headers()))
    return [slim_repo(r) for r in data.get("items", [])]


def get_repo(full_name: str) -> dict:
    """Fetch one repo by 'owner/name' (also accepts a full github.com URL)."""
    full_name = full_name.strip().removeprefix("https://").removeprefix("http://")
    full_name = full_name.removeprefix("github.com/").strip("/")
    owner, _, name = full_name.partition("/")
    name = name.split("/")[0].removesuffix(".git")
    if not owner or not name:
        raise ValueError(f"Expected 'owner/repo', got {full_name!r}")
    data = json.loads(http_get(f"{API}/repos/{owner}/{name}", headers=_headers()))
    return slim_repo(data)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("query", nargs="?", help="What to search for, e.g. 'authentication'")
    p.add_argument("--repo", help="Fetch a single repo instead, e.g. owner/name")
    p.add_argument("--language", help="Only repos in this language, e.g. TypeScript")
    p.add_argument("--min-stars", type=int, default=50)
    p.add_argument("--limit", type=int, default=15)
    args = p.parse_args()
    if args.repo:
        result = get_repo(args.repo)
    elif args.query:
        result = search_repos(args.query, args.language, args.min_stars, args.limit)
    else:
        p.error("give a query or --repo")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
