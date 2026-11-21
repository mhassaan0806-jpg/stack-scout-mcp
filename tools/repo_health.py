"""Decide whether a repo is alive, free and trustworthy, and give it a 0-100 score.

Hard rejects (never recommended):
    - reading material, not a tool (awesome-lists, tutorials, guides, courses)
    - archived on GitHub
    - no code pushed for over 2 years
    - source-available / non-free license (see license_check.py)

Score = popularity (0-40) + recency (0-40) + license (0-20)
    popularity: 8 * log10(stars + 1)  -> 100 stars ~16, 1k ~24, 10k ~32, 100k = 40
    recency:    pushed <= 90 days 40, <= 180 32, <= 365 22, <= 730 10
    license:    see license_check.py (permissive 20 ... unknown 0). If the repo dict has
                'license_info' (read from the LICENSE file by research_tool.resolve_license),
                that is used instead of GitHub's label.

CLI:
    python tools/repo_health.py medusajs/medusa saleor/saleor
"""
from __future__ import annotations

import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # allow `python tools/x.py`
from tools.license_check import classify  # noqa: E402

STALE_DAYS = 730

# Repos named like these are reading material (lists, courses), not tools you can build with.
_NOT_A_TOOL = re.compile(
    r"(^awesome|awesome-|tutorial|guide|interview|roadmap|cheat-?sheet|\d+-days|^learn-|-course$|"
    r"-examples?$|^examples?$|-book$|-notes$|-resources$)",
    re.I,
)


def days_since(iso: str | None, now: datetime | None = None) -> int | None:
    if not iso:
        return None
    then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return ((now or datetime.now(timezone.utc)) - then).days


def _recency_points(age: int) -> int:
    if age <= 90:
        return 40
    if age <= 180:
        return 32
    if age <= 365:
        return 22
    return 10


def assess(repo: dict, now: datetime | None = None) -> dict:
    """Return {'status': ok|caution|rejected, 'score', 'rejected_because', 'warnings', 'license', 'days_since_push'}."""
    rejects: list[str] = []
    warnings: list[str] = []
    lic = repo.get("license_info") or classify(repo.get("license"))  # license_info: read from LICENSE file
    age = days_since(repo.get("pushed_at"), now)
    stars = repo.get("stars", 0)

    if _NOT_A_TOOL.search(repo.get("full_name", "").split("/")[-1]):
        rejects.append("a list or tutorial, not a tool")
    if repo.get("archived"):
        rejects.append("archived (owner stopped maintaining it)")
    if age is None or age > STALE_DAYS:
        rejects.append(f"no code changes in {age} days" if age is not None else "no activity data")
    if lic["category"] == "not-free":
        rejects.append(f"{lic['spdx']} license is not open source")
    if repo.get("fork"):
        warnings.append("this is a fork; check whether the original is the better choice")
    if age is not None and 365 < age <= STALE_DAYS:
        warnings.append("slowing down: last code change over a year ago")
    if lic["category"] == "unknown":
        warnings.append("license unclear; read it before using")
    elif lic["category"] == "copyleft":
        warnings.append(f"{lic['spdx']}: {lic['note']}")
    elif lic["category"] == "open-core":
        warnings.append(lic["note"])
    if stars < 100:
        warnings.append("small community (under 100 stars)")

    if rejects:
        return {"status": "rejected", "score": 0, "rejected_because": rejects, "warnings": warnings,
                "license": lic, "days_since_push": age}

    score = min(40, round(8 * math.log10(stars + 1))) + _recency_points(age) + lic["points"]
    return {
        "status": "caution" if warnings else "ok",
        "score": score,
        "rejected_because": [],
        "warnings": warnings,
        "license": lic,
        "days_since_push": age,
    }


def main() -> None:
    from tools.github_search import get_repo

    if len(sys.argv) < 2:
        sys.exit("usage: python tools/repo_health.py owner/repo [owner/repo ...]")
    out = []
    for name in sys.argv[1:]:
        repo = get_repo(name)
        out.append({**repo, "health": assess(repo)})
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
