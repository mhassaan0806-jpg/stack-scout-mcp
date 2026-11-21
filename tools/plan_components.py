"""Backup planner: guess the building blocks of a request (auth, payments, cart...) from keywords.

The user's AI is the real planner. It splits any request into needs and passes them
to scout_stack. This file only runs when it doesn't. A request that matches no known
pattern ("a 2D game engine") is searched as typed. If it sounds like an app
("...app", "...website"), common app blocks are added too.

CLI:
    python tools/plan_components.py "I want to build an online shoe store"
    python tools/plan_components.py --list
"""
from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # allow `python tools/x.py`
from tools._common import DATA_DIR  # noqa: E402


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    return json.loads((DATA_DIR / "components.json").read_text(encoding="utf-8"))


_APP_WORDS = ["app", "apps", "website", "web app", "platform", "portal", "saas", "service", "mobile app"]


def _matches(text: str, keyword: str) -> bool:
    return re.search(rf"\b{re.escape(keyword.lower())}\b", text) is not None


def plan_components(idea: str) -> dict:
    """Return {'archetypes': [...], 'components': [{'id', 'name', 'why'}...]} for an idea."""
    catalog = load_catalog()
    text = idea.lower()
    picked: dict[str, str] = {}  # component id -> reason (first reason wins, order preserved)
    archetypes = []

    for arch_name, arch in catalog["archetypes"].items():
        hit = next((k for k in arch["keywords"] if _matches(text, k)), None)
        if hit:
            archetypes.append(arch_name)
            for cid in arch["components"]:
                picked.setdefault(cid, f"common in {arch_name} apps; you said '{hit}'")

    for cid, comp in catalog["components"].items():
        hit = next((k for k in comp["keywords"] if _matches(text, k)), None)
        if hit:
            picked.setdefault(cid, f"you mentioned '{hit}'")

    components = [
        {"id": cid, "name": catalog["components"][cid]["name"], "why": why} for cid, why in picked.items()
    ]
    if not picked:
        # Not a pattern we know: search for the request itself, as typed.
        components.append({"id": idea.strip(), "name": idea.strip(),
                           "why": "searched as you described it (no known building block matched)"})
        if any(_matches(text, w) for w in _APP_WORDS):
            for cid in catalog["default_components"]:
                components.append({"id": cid, "name": catalog["components"][cid]["name"],
                                   "why": "common building block for most apps"})

    return {"idea": idea, "archetypes": archetypes, "components": components}


def list_components() -> list[dict]:
    return [{"id": cid, "name": c["name"], "query": c["query"]} for cid, c in load_catalog()["components"].items()]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit('usage: python tools/plan_components.py "your app idea"  |  --list')
    if sys.argv[1] == "--list":
        print(json.dumps(list_components(), indent=2))
    else:
        print(json.dumps(plan_components(" ".join(sys.argv[1:])), indent=2))
