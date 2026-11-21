"""Full pipeline: needs -> GitHub search -> license check -> filter & rank -> research top picks -> report.

Works for any request. The user's AI should split the request into needs and pass
them as `components`. Each need can be a catalog id ("auth") or plain words
("extract text from PDF files in python"). Without components, plan_components.py
makes a keyword-based guess.

CLI:
    python tools/scout_stack.py "online shoe store"
    python tools/scout_stack.py "online shoe store" --components auth,payments,ecommerce --language TypeScript
    python tools/scout_stack.py "pdf tool" --components "extract text from pdf files in python"
    python tools/scout_stack.py "online shoe store" --no-research --out .tmp/shoe.md --json .tmp/shoe.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # allow `python tools/x.py`
from tools._common import FetchError, RateLimitError  # noqa: E402
from tools.format_report import format_report  # noqa: E402
from tools.github_search import search_repos  # noqa: E402
from tools.license_check import classify  # noqa: E402
from tools.plan_components import load_catalog, plan_components  # noqa: E402
from tools.rank_tools import rank  # noqa: E402
from tools.research_tool import research_many, resolve_license  # noqa: E402

# Words that carry no search meaning. GitHub requires every search word to match, so they must go.
_FILLER = set(
    "i im i'm want wanna need needs to build make create a an the for with my me that which who app apps "
    "application website site tool tools library libraries lib package framework free open source open-source "
    "best good great some something looking find help in of and or using use can is it like we our web simple "
    "easy way ways how do does should would could please recommend recommendation any on from into by "
    "self-hosted selfhosted alternative file files stuff things thing software program system".split()
)
# Action words narrow GitHub search too much ("extract text pdf" misses PyMuPDF), so the second,
# broader search drops them.
_VERBS = set(
    "extract convert send build generate create manage track parse read write store show display render edit "
    "upload download sync monitor schedule scan process analyze analyse run host deploy automate add get "
    "handle accept take let allow".split()
)
_LANGUAGES = {
    "python": "Python", "typescript": "TypeScript", "javascript": "JavaScript", "js": "JavaScript",
    "ts": "TypeScript", "node": "JavaScript", "nodejs": "JavaScript", "golang": "Go", "rust": "Rust",
    "java": "Java", "kotlin": "Kotlin", "swift": "Swift", "php": "PHP", "ruby": "Ruby", "dart": "Dart",
    "flutter": "Dart", "c#": "C#", "csharp": "C#", "dotnet": "C#", "c++": "C++", "cpp": "C++", "elixir": "Elixir",
    "scala": "Scala", "haskell": "Haskell", "lua": "Lua", "r": "R",
}


def search_terms(text: str) -> tuple[list[str], str | None]:
    """Turn plain words into GitHub search terms, pulling out a programming language if named.

    'extract text from PDF files in python' -> (['extract', 'text', 'pdf', 'files'], 'Python')
    """
    language = None
    terms = []
    for word in re.findall(r"[a-z0-9][a-z0-9+#.\-]*", text.lower()):
        word = word.strip(".-")
        if word in _LANGUAGES and language is None:
            language = _LANGUAGES[word]
        elif word and word not in _FILLER and word not in terms:
            terms.append(word)
    return terms[:5], language


def _resolve(component: str) -> tuple[str, dict | None]:
    """Map a component id or display name to its catalog entry (None = free text)."""
    catalog = load_catalog()["components"]
    key = component.strip().lower().replace(" ", "_")
    if key in catalog:
        return key, catalog[key]
    for cid, entry in catalog.items():
        if entry["name"].lower() == component.strip().lower():
            return cid, entry
    return component.strip(), None


def _free_text_candidates(text: str, language: str | None, min_stars: int, top_n: int,
                          notes: list[str]) -> tuple[list[dict], str, str | None]:
    """Two searches, merged: all key words (precise), then the nouns only (broader). Max 3 searches."""
    terms, named_lang = search_terms(text)
    lang = language or named_lang
    if not terms:
        raise ValueError(f"Couldn't find searchable words in {text!r}. Describe the need in a few words.")
    precise = " ".join(terms)
    nouns = [t for t in terms if t not in _VERBS] or terms
    broad = " ".join(nouns[:2])
    attempts = [precise] + ([broad] if broad != precise else [])
    found: list[dict] = []
    for query in attempts:
        found += search_repos(query, lang, min_stars)
    if lang and len({r["full_name"] for r in found}) < top_n:
        notes.append(f"Few {lang} results, so tools in other languages are included too.")
        found += search_repos(broad, None, min_stars)
    return found, " | ".join(attempts), lang


def scout_component(component: str, language: str | None = None, top_n: int = 3,
                    min_stars: int = 50, research: bool = True) -> dict:
    cid, entry = _resolve(component)
    notes: list[str] = []
    if entry:
        name, query, terms = entry["name"], entry["query"], None
        lang = language if (language and entry["language_sensitive"]) else None
        candidates = search_repos(query, lang, min_stars)
        if lang and len(candidates) < top_n:
            notes.append(f"Few {lang} results, so tools in other languages are included too.")
            candidates += search_repos(query, None, min_stars)
    else:
        name = component.strip()
        candidates, query, lang = _free_text_candidates(component, language, min_stars, top_n, notes)
        terms = search_terms(component)[0]

    # GitHub's license label isn't enough for "Other" or BUSL-style labels: read those LICENSE files.
    unclear = [c for c in candidates if classify(c.get("license"))["category"] in ("unknown", "not-free")]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(resolve_license, unclear))
        # Then read the license of every pick (open core can hide behind an "MIT" label) and re-rank.
        for _ in range(2):
            ranked = rank(candidates, top_n, terms)
            picks = {r["full_name"] for r in ranked["top"]}
            unread = [c for c in candidates if c["full_name"] in picks and "license_info" not in c]
            if not unread:
                break
            list(pool.map(lambda c: resolve_license(c, force=True), unread))
    ranked = rank(candidates, top_n, terms)
    if research:
        for repo, notes_for_repo in zip(ranked["top"], research_many(ranked["top"])):
            repo["research"] = notes_for_repo
    return {"id": cid, "name": name, "query": query, "language_filter": lang, "notes": notes, **ranked}


def scout(idea: str = "", components: list[str] | None = None, language: str | None = None,
          top_n: int = 3, min_stars: int = 50, research: bool = True) -> dict:
    whys: dict[str, str] = {}
    if not components:
        plan = plan_components(idea)
        components = [c["id"] for c in plan["components"]]
        whys = {c["id"]: c["why"] for c in plan["components"]}

    def failed(comp: str, error: str) -> dict:
        cid, entry = _resolve(comp)
        return {"id": cid, "name": entry["name"] if entry else comp, "error": error,
                "top": [], "rejected": [], "considered": 0}

    out = []
    rate_limited: str | None = None
    for comp in components:
        if rate_limited:
            out.append(failed(comp, rate_limited))
            continue
        try:
            result = scout_component(comp, language, top_n, min_stars, research=False)
        except RateLimitError as e:
            rate_limited = (f"{e} GitHub allows 10 free searches a minute without a token. "
                            "Wait a minute and ask again (finished needs are cached), "
                            "or add a free GITHUB_TOKEN to .env for 30 a minute.")
            result = failed(comp, rate_limited)
        except (FetchError, ValueError) as e:
            result = failed(comp, str(e))
        if comp in whys:
            result["why"] = whys[comp]
        out.append(result)

    if research:  # searches are rate limited so they run in order; research has no quota, so do it all at once
        picks = [repo for result in out for repo in result["top"]]
        for repo, notes in zip(picks, research_many(picks, workers=12)):
            repo["research"] = notes

    return {
        "idea": idea,
        "language": language,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "components": out,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("idea", help="What the user wants to build, in plain words")
    p.add_argument("--components", help="Comma-separated needs (catalog ids or plain words) instead of auto-planning")
    p.add_argument("--language", help="Preferred language for code libraries, e.g. TypeScript, Python")
    p.add_argument("--top", type=int, default=3, help="Tools to list per need (default 3)")
    p.add_argument("--min-stars", type=int, default=50)
    p.add_argument("--no-research", action="store_true", help="Skip in-depth research of top picks (faster)")
    p.add_argument("--out", help="Write the Markdown report here (e.g. .tmp/report.md)")
    p.add_argument("--json", help="Write the raw results as JSON here")
    args = p.parse_args()

    comps = [c.strip() for c in args.components.split(",") if c.strip()] if args.components else None
    result = scout(args.idea, comps, args.language, args.top, args.min_stars, not args.no_research)
    report = format_report(result)
    for path, content in ((args.out, report), (args.json, json.dumps(result, indent=2))):
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(content, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
