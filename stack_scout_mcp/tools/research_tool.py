"""Research one tool in depth from free public sources, so the user's AI can judge it honestly.

Collects facts only. The user's AI turns them into pros, cons, the catch and fit.
No source here needs a key, and none uses the GitHub API quota:

  README          raw.githubusercontent.com: paid/cloud mentions, self-hosting needs, maturity flags
  LICENSE file    only when GitHub can't name the license: open-core / restrictive terms
  Releases feed   github.com/<repo>/releases.atom: latest release and date
  deps.dev        (Google) OpenSSF Scorecard + packages published from the repo
  OSV via deps.dev  known security advisories in the main package's latest version
  npm/PyPI/crates download counts for that package
  Hacker News     (Algolia API) discussions linking the repo or its website

CLI:
    python -m stack_scout_mcp.tools.research_tool medusajs/medusa
    python -m stack_scout_mcp.tools.research_tool medusajs/medusa --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ._common import FetchError, RateLimitError
from ._common import http_get as _http_get
from .license_check import classify, classify_text

DAY = 24 * 60 * 60
RAW = "https://raw.githubusercontent.com/{repo}/HEAD/{path}"
DEPS = "https://api.deps.dev/v3"
README_NAMES = ["README.md", "readme.md", "README.rst", "Readme.md", "README", "README.markdown"]
LICENSE_NAMES = ["LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "COPYING", "license", "LICENSE-MIT"]

_PAID = re.compile(
    r"\b(enterprise|pricing|paid|premium|commercial|license key|subscription|free tier|free plan|pro plan|"
    r"cloud (?:version|offering|plan|service|edition)|hosted (?:version|service|offering)|managed (?:service|cloud))\b",
    re.I,
)
_MATURITY = re.compile(
    r"\b(alpha|beta|experimental|work in progress|not (?:yet )?(?:ready|recommended) for production|"
    r"breaking changes|unstable|deprecated|no longer maintained|unmaintained|looking for (?:new )?maintainers)\b",
    re.I,
)
_NEEDS = {
    "Docker": r"\bdocker\b",
    "Kubernetes / Helm": r"\b(?:kubernetes|helm|k8s)\b",
    "PostgreSQL": r"\bpostgres(?:ql)?\b",
    "MySQL / MariaDB": r"\b(?:mysql|mariadb)\b",
    "MongoDB": r"\bmongo(?:db)?\b",
    "Redis": r"\bredis\b",
    "Elasticsearch": r"\belasticsearch\b",
    "ClickHouse": r"\bclickhouse\b",
    "Node.js": r"\bnode\.?js\b|\bnpm (?:install|i)\b|\bnpx\b",
    "Python": r"\bpip install\b|\bpython3?\b",
    "Go": r"\bgo install\b|\bgolang\b",
    "Java / JVM": r"\bjava\b|\bmaven\b|\bgradle\b",
    "PHP": r"\bphp\b|\bcomposer (?:require|install)\b",
    "Ruby": r"\bgem install\b|\bbundle install\b",
    ".NET": r"\bdotnet\b|\.net (?:core|\d)",
    "Rust": r"\bcargo (?:install|add)\b",
    "S3-compatible storage": r"\bs3\b",
    "GPU": r"\bgpu\b|\bcuda\b",
}
_RAM = re.compile(r"\b\d+\s?gb (?:of )?ram\b", re.I)


def http_get(url: str, **kw) -> str:
    return _http_get(url, ttl=kw.pop("ttl", DAY), **kw)


def _first_raw(full_name: str, names: list[str]) -> str | None:
    for name in names:
        try:
            return http_get(RAW.format(repo=full_name, path=name))
        except (FetchError, RateLimitError):
            continue
    return None


# ---------- License ----------

def resolve_license(repo: dict, force: bool = False) -> dict:
    """Read the LICENSE file when GitHub's label isn't enough. Sets repo['license_info'].

    Always read for 'unknown' (GitHub couldn't name it) and 'not-free' (could be an open-core
    repo whose enterprise part is BUSL). With force=True, read it anyway to catch open-core
    repos GitHub labels plain MIT/Apache.
    """
    info = classify(repo.get("license"))
    if force or info["category"] in ("unknown", "not-free"):
        text = _first_raw(repo["full_name"], LICENSE_NAMES)
        detected = classify_text(text) if text else None
        if detected and detected["category"] != "unknown":
            info = detected
    repo["license_info"] = info
    return repo


# ---------- README ----------

def _clean_lines(markdown: str) -> list[str]:
    out, in_code = [], False
    for raw in markdown.splitlines():
        if raw.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        line = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", raw)          # images / badges
        line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)      # links -> text
        line = re.sub(r"<[^>]+>", "", line)                       # html
        line = re.sub(r"[#>*_`|]+", " ", line)
        line = " ".join(line.split())
        if len(line) > 25:
            out.append(line)
    return out


_STRONG_PAID = re.compile(r"\b(enterprise|paid|premium|commercial|license key|proprietary)\b", re.I)


def _matching_lines(lines: list[str], pattern: re.Pattern, limit: int = 4) -> list[str]:
    found = []
    for line in lines:
        if pattern.search(line) and line not in found:
            found.append(line)
    found.sort(key=lambda l: not _STRONG_PAID.search(l))  # strongest signals first, otherwise README order
    return [l if len(l) <= 220 else l[:219].rstrip() + "…" for l in found[:limit]]


def readme_signals(markdown: str) -> dict:
    lines = _clean_lines(markdown)
    lowered = markdown.lower()
    needs = [name for name, pat in _NEEDS.items() if re.search(pat, lowered)]
    ram = _RAM.search(markdown)
    if ram:
        needs.append(f"hardware: {ram.group(0)}")
    return {
        "summary": next((l for l in lines if not l.lower().startswith(("table of contents", "contents"))), ""),
        "paid_mentions": _matching_lines(lines, _PAID),
        "maturity_flags": _matching_lines(lines, _MATURITY, limit=3),
        "mentions_needing": needs,
        "length": len(markdown),
    }


# ---------- Releases ----------

def latest_release(full_name: str) -> dict | None:
    xml = http_get(f"https://github.com/{full_name}/releases.atom")
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entry = ET.fromstring(xml).find("a:entry", ns)
    if entry is None:
        return None
    return {"title": (entry.findtext("a:title", "", ns) or "").strip(), "date": entry.findtext("a:updated", "", ns)[:10]}


# ---------- deps.dev, OSV, downloads ----------

def _project_id(full_name: str) -> str:
    return urllib.parse.quote(f"github.com/{full_name.lower()}", safe="")


def scorecard(full_name: str) -> dict | None:
    data = json.loads(http_get(f"{DEPS}/projects/{_project_id(full_name)}"))
    sc = data.get("scorecard")
    if not sc:
        return None
    checks = {c["name"]: c["score"] for c in sc.get("checks", []) if c.get("score", -1) >= 0}
    return {"score": sc.get("overallScore"), "date": (sc.get("date") or "")[:10], "checks": checks}


def _publishes(system: str, name: str, full_name: str) -> bool:
    """True if deps.dev says this package's latest version comes from this repo."""
    q = urllib.parse.quote(name, safe="")
    try:
        pkg = json.loads(http_get(f"{DEPS}/systems/{system.lower()}/packages/{q}"))
        default = next((v["versionKey"]["version"] for v in pkg.get("versions", []) if v.get("isDefault")), None)
        if not default:
            return False
        ver = json.loads(http_get(f"{DEPS}/systems/{system.lower()}/packages/{q}/versions/"
                                  f"{urllib.parse.quote(default, safe='')}"))
    except (FetchError, RateLimitError, ValueError):
        return False
    target = f"github.com/{full_name.lower()}"
    return any(p.get("projectKey", {}).get("id", "").lower() == target for p in ver.get("relatedProjects", []))


def main_package(full_name: str) -> dict | None:
    """The package this repo publishes that best matches its name: {'system', 'name'}."""
    data = json.loads(http_get(f"{DEPS}/projects/{_project_id(full_name)}:packageversions"))
    pkgs: list[tuple[str, str]] = []
    for v in data.get("versions", []):
        key = (v["versionKey"]["system"], v["versionKey"]["name"])
        if key not in pkgs:
            pkgs.append(key)
    if not pkgs:
        return None
    owner, repo_name = (s.lower() for s in full_name.split("/"))

    def closeness(p: tuple[str, str]) -> int:
        bare = p[1].lower().split("/")[-1].split(":")[-1]
        return 0 if bare == repo_name else 1 if repo_name in p[1].lower() else 2

    system, name = min(pkgs, key=closeness)
    if closeness((system, name)) > 0:
        # deps.dev's list can be cut short for big monorepos: try the obvious names directly.
        for guess_system in dict.fromkeys(s for s, _ in pkgs):
            guesses = [repo_name] + ([f"@{owner}/{repo_name}"] if guess_system == "NPM" else [])
            hit = next((g for g in guesses if _publishes(guess_system, g, full_name)), None)
            if hit:
                system, name = guess_system, hit
                break
    return {"system": system, "name": name, "published_packages": len(pkgs)}


def downloads(system: str, name: str) -> dict | None:
    if system == "NPM":
        d = json.loads(http_get(f"https://api.npmjs.org/downloads/point/last-month/{name}"))
        return {"count": d.get("downloads", 0), "period": "last month"}
    if system == "PYPI":
        d = json.loads(http_get(f"https://pypistats.org/api/packages/{name.lower()}/recent"))
        return {"count": d["data"]["last_month"], "period": "last month"}
    if system == "CARGO":
        d = json.loads(http_get(f"https://crates.io/api/v1/crates/{name}"))
        return {"count": d["crate"].get("recent_downloads", 0), "period": "last 90 days"}
    return None


def advisories(system: str, name: str) -> dict | None:
    """Known advisories (OSV) affecting the package's default (latest) version."""
    q = urllib.parse.quote(name, safe="")
    pkg = json.loads(http_get(f"{DEPS}/systems/{system.lower()}/packages/{q}"))
    default = next((v["versionKey"]["version"] for v in pkg.get("versions", []) if v.get("isDefault")), None)
    if not default:
        return None
    ver = json.loads(http_get(f"{DEPS}/systems/{system.lower()}/packages/{q}/versions/{urllib.parse.quote(default, safe='')}"))
    ids = [a["id"] for a in ver.get("advisoryKeys", [])]
    return {"version": default, "count": len(ids), "ids": ids[:5]}


# ---------- Hacker News ----------

def hn_discussions(full_name: str, homepage: str | None) -> dict:
    queries = [f"github.com/{full_name}"]
    host = urllib.parse.urlparse(homepage or "").netloc.removeprefix("www.")
    if host and "github" not in host:
        queries.append(host)
    stories: dict[str, dict] = {}
    for q in queries:
        params = urllib.parse.urlencode(
            {"query": q, "restrictSearchableAttributes": "url", "tags": "story", "hitsPerPage": 20}
        )
        for h in json.loads(http_get(f"https://hn.algolia.com/api/v1/search?{params}")).get("hits", []):
            stories[h["objectID"]] = {
                "title": h.get("title") or "",
                "points": h.get("points") or 0,
                "comments": h.get("num_comments") or 0,
                "year": (h.get("created_at") or "")[:4],
                "url": f"https://news.ycombinator.com/item?id={h['objectID']}",
            }
    # Stories about the tool (its name in the title) before ones that merely link its website.
    name = full_name.split("/")[-1].lower()
    top = sorted(stories.values(), key=lambda s: (name in s["title"].lower(), s["points"]), reverse=True)
    return {"stories": len(top), "top": top[:3]}


# ---------- Put it together ----------

def research(repo: dict) -> dict:
    """Collect every free signal for one repo (from github_search.slim_repo). Never raises."""
    full = repo["full_name"]
    notes: dict = {"repo": full, "unavailable": []}

    def attempt(label: str, fn, *args):
        try:
            return fn(*args)
        except (FetchError, RateLimitError, ValueError, KeyError, ET.ParseError):
            notes["unavailable"].append(label)
            return None

    if "license_info" not in repo:
        resolve_license(repo)
    notes["license_info"] = repo["license_info"]
    readme = _first_raw(full, README_NAMES)
    notes["readme"] = readme_signals(readme) if readme else None
    if readme is None:
        notes["unavailable"].append("README")
    notes["latest_release"] = attempt("releases", latest_release, full)
    notes["scorecard"] = attempt("OpenSSF Scorecard", scorecard, full)
    pkg = attempt("package registry", main_package, full)
    if pkg:
        pkg["downloads"] = attempt("download counts", downloads, pkg["system"], pkg["name"])
        pkg["advisories"] = attempt("security advisories", advisories, pkg["system"], pkg["name"])
    notes["package"] = pkg
    notes["hacker_news"] = attempt("Hacker News", hn_discussions, full, repo.get("homepage"))
    return notes


def research_many(repos: list[dict], workers: int = 8) -> list[dict]:
    """Research several repos in parallel; results in the same order."""
    if not repos:
        return []
    with ThreadPoolExecutor(max_workers=min(workers, len(repos))) as pool:
        return list(pool.map(research, repos))


def main() -> None:
    from .format_report import format_research
    from .github_search import get_repo
    from .repo_health import assess

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("repo", help="owner/name or a github.com URL")
    p.add_argument("--json", action="store_true", help="Print raw JSON instead of Markdown")
    args = p.parse_args()
    repo = resolve_license(get_repo(args.repo))
    notes = research(repo)
    sys.stdout.reconfigure(encoding="utf-8")
    if args.json:
        print(json.dumps({"repo": repo, "health": assess(repo), "research": notes}, indent=2))
    else:
        print("\n".join(format_research({**repo, "health": assess(repo), "research": notes})))


if __name__ == "__main__":
    main()
