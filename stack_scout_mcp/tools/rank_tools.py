"""Filter and rank candidate repos for one building block.

Final rank = health score (0-100, see repo_health.py) + relevance bonus (0-15 or 0-25).
Catalog needs: bonus follows GitHub's best-match order (0-15).
Plain-language needs: bonus = share of the key words the repo mentions (0-25), so a
hugely popular but loosely related repo doesn't beat a focused, healthy one.

CLI (reads the JSON list printed by github_search.py):
    python -m stack_scout_mcp.tools.github_search "topic:payments" > .tmp/payments.json
    python -m stack_scout_mcp.tools.rank_tools .tmp/payments.json --top 3
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .repo_health import assess

RELEVANCE_MAX = 15
TERM_RELEVANCE_MAX = 25  # plain-language searches are noisier, so matching the words counts more


def _term_relevance(repo: dict, terms: list[str]) -> float:
    """Share of search terms found in the repo's name, description and topics (0-1)."""
    haystack = " ".join([repo["full_name"], repo.get("description") or "", " ".join(repo.get("topics") or [])]).lower()
    return sum(t in haystack for t in terms) / len(terms)


def rank(candidates: list[dict], top_n: int = 3, terms: list[str] | None = None) -> dict:
    """Return {'top': [...], 'rejected': [...], 'considered': int}. Each repo gains 'health' and 'rank_score'.

    With `terms` (plain-language searches), relevance = share of terms the repo mentions.
    Without (tuned catalog searches), relevance = GitHub's best-match position.
    """
    seen: set[str] = set()
    kept, rejected = [], []
    total = len(candidates) or 1
    for position, repo in enumerate(candidates):
        key = repo["full_name"].lower()
        if key in seen:
            continue
        seen.add(key)
        health = assess(repo)
        if terms:
            relevance = round(TERM_RELEVANCE_MAX * _term_relevance(repo, terms))
        else:
            relevance = round(RELEVANCE_MAX * (1 - position / total))
        entry = {**repo, "health": health, "rank_score": health["score"] + relevance if health["score"] else 0}
        (rejected if health["status"] == "rejected" else kept).append(entry)
    kept.sort(key=lambda r: r["rank_score"], reverse=True)
    return {"top": kept[:top_n], "rejected": rejected, "considered": len(seen)}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("candidates_json", help="File with a JSON list of repos (from github_search.py)")
    p.add_argument("--top", type=int, default=3)
    args = p.parse_args()
    candidates = json.loads(Path(args.candidates_json).read_text(encoding="utf-8"))
    print(json.dumps(rank(candidates, args.top), indent=2))


if __name__ == "__main__":
    main()
