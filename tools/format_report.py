"""Turn scout / research results (dicts) into Markdown the user's AI can read and build on.

The report holds facts only. The closing "For the AI" note tells the assistant
to write the pros, cons, catch and fit from these facts, not from memory.

CLI (reads the JSON written by `scout_stack.py --json`):
    python tools/format_report.py .tmp/scout_result.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

AI_NOTE = (
    "**For the AI presenting this:** for each need, recommend one pick and say why it fits this project. "
    "Give honest pros, cons, the catch (paid parts, license duties, hosting it needs), and technical limits, "
    "using only the facts above and the linked pages. Say \"unknown\" rather than guess. If a well-known "
    "paid service is the usual choice for a need, mention it briefly and label it paid."
)

CATEGORY_LABEL = {
    "permissive": "free, permissive",
    "weak-copyleft": "free, weak copyleft",
    "copyleft": "free, copyleft",
    "open-core": "open core: some parts paid",
    "unknown": "unclear",
    "not-free": "not free",
}


def _num(n: int) -> str:
    for size, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1000, "k")):
        if n >= size:
            return f"{n / size:.1f}{suffix}".replace(f".0{suffix}", suffix)
    return str(n)


def _age(days: int | None) -> str:
    if days is None:
        return "unknown"
    if days < 1:
        return "today"
    if days < 60:
        return f"{days} day{'s' if days != 1 else ''} ago"
    if days < 730:
        return f"{days // 30} months ago"
    return f"{days // 365} years ago"


def _cell(text: str, width: int = 90) -> str:
    text = " ".join((text or "").split()).replace("|", "\\|")
    return text if len(text) <= width else text[: width - 1].rstrip() + "…"


def _license_text(health: dict) -> str:
    lic = health["license"]
    return f"{lic['spdx'] or 'none found'} ({CATEGORY_LABEL[lic['category']]})"


def format_repo_table(repos: list[dict]) -> list[str]:
    lines = [
        "| # | Tool | What it is | Stars | Last code change | License | Score |",
        "|---|------|------------|-------|------------------|---------|-------|",
    ]
    for i, r in enumerate(repos, 1):
        h = r["health"]
        lines.append(
            f"| {i} | [{r['full_name']}]({r['url']}) | {_cell(r['description'])} | {_num(r['stars'])} "
            f"| {_age(h['days_since_push'])} | {_license_text(h)} | {h['score']} |"
        )
    return lines


def format_research(repo: dict) -> list[str]:
    """Research notes for one repo (needs repo['health'] and repo['research'])."""
    h, notes = repo["health"], repo.get("research") or {}
    lic = h["license"]
    lines = [f"#### {repo['full_name']}: research notes", ""]
    if repo.get("homepage"):
        lines.append(f"- **Website:** {repo['homepage']}")
    lines.append(f"- **License:** {_license_text(h)}. {lic['note']}"
                 + (" (read from the LICENSE file)" if lic.get("detected_from") else ""))

    readme = notes.get("readme")
    if readme and readme["paid_mentions"]:
        lines.append("- **README mentions paid / cloud / enterprise terms** (read in context):")
        lines += [f"  - \"{m}\"" for m in readme["paid_mentions"]]

    activity = [f"last code change {_age(h['days_since_push'])}"]
    rel = notes.get("latest_release")
    if rel:
        activity.append(f"latest release {rel['title'] or '(untitled)'} on {rel['date']}")
    activity.append(f"{_num(repo.get('open_issues', 0))} open issues and PRs")
    lines.append(f"- **Activity:** {', '.join(activity)}")

    adoption = [f"{_num(repo['stars'])} GitHub stars"]
    pkg = notes.get("package")
    if pkg:
        dl = pkg.get("downloads")
        dl_text = f", {_num(dl['count'])} downloads {dl['period']}" if dl else ""
        adoption.append(f"package `{pkg['name']}` on {pkg['system'].lower()}{dl_text}")
    lines.append(f"- **Adoption:** {', '.join(adoption)}")

    sc = notes.get("scorecard")
    if sc and sc.get("score") is not None:
        weak = sorted((v, k) for k, v in sc["checks"].items() if v <= 3)[:4]
        weak_text = f"; weak spots: {', '.join(f'{k} {v}/10' for v, k in weak)}" if weak else ""
        lines.append(f"- **Security practices (OpenSSF Scorecard):** {sc['score']}/10{weak_text}")
    adv = (pkg or {}).get("advisories")
    if adv is not None:
        if adv["count"]:
            lines.append(f"- **Known vulnerabilities in latest version ({adv['version']}):** "
                         f"{adv['count']} ({', '.join(adv['ids'])})")
        else:
            lines.append(f"- **Known vulnerabilities in latest version ({adv['version']}):** none listed in OSV")

    hn = notes.get("hacker_news")
    if hn and hn["stories"]:
        top = "; ".join(f"[{s['title']}]({s['url']}) ({s['points']} points, {s['comments']} comments, {s['year']})"
                        for s in hn["top"])
        lines.append(f"- **Hacker News:** {hn['stories']} stories link to it. Top: {top}")
    elif hn is not None:
        lines.append("- **Hacker News:** no stories link to it")

    if readme and readme["mentions_needing"]:
        lines.append(f"- **README mentions (likely setup needs):** {', '.join(readme['mentions_needing'])}")
    if readme and readme["maturity_flags"]:
        lines.append("- **Maturity flags in README:**")
        lines += [f"  - \"{m}\"" for m in readme["maturity_flags"]]
    for w in h["warnings"]:
        lines.append(f"- **Watch out:** {w}")
    if notes.get("unavailable"):
        lines.append(f"- _Couldn't check: {', '.join(notes['unavailable'])}_")
    lines.append("")
    return lines


def format_component(comp: dict, number: int | None = None) -> list[str]:
    lines = [f"## {number}. {comp['name']}" if number else f"## {comp['name']}"]
    if comp.get("why"):
        lines.append(f"_Why: {comp['why']}_")
    lines.append("")
    if comp.get("error"):
        lines += [f"Not searched: {comp['error']}", ""]
        return lines
    if comp["top"]:
        lines += format_repo_table(comp["top"])
    else:
        lines.append(f"No free, maintained tool found (searched GitHub for `{comp.get('query', '')}`). "
                     "Try describing the need in different words.")
    if comp.get("rejected"):
        skipped = ", ".join(f"{r['full_name']} ({r['health']['rejected_because'][0]})" for r in comp["rejected"][:5])
        lines += ["", f"Skipped: {skipped}"]
    for note in comp.get("notes", []):
        lines += ["", f"Note: {note}"]
    lines.append("")
    researched = [r for r in comp["top"] if r.get("research")]
    if researched:
        for r in researched:
            lines += format_research(r)
    else:
        warnings = [(r["full_name"], w) for r in comp["top"] for w in r["health"]["warnings"]]
        if warnings:
            lines += ["Watch out:"] + [f"- {name}: {w}" for name, w in warnings] + [""]
    return lines


def format_report(result: dict) -> str:
    comps = result["components"]
    checked = sum(c.get("considered", 0) for c in comps)
    skipped = sum(len(c.get("rejected", [])) for c in comps)
    lang = result.get("language")
    lines = [
        f"# Free tool stack for: {result['idea']}" if result.get("idea") else "# Free tool stack",
        "",
        f"{len(comps)} need{'s' if len(comps) != 1 else ''} · {checked} repos checked · "
        f"{skipped} skipped as archived, stale, not free, or not a tool"
        + (f" · language: {lang} (applied to code libraries only)" if lang else ""),
        "",
        "Listed tools are open source (or open core, flagged), not archived, and had code changes in the "
        "last 2 years. Score (0-100) = popularity + recent activity + how free the license is.",
        "",
    ]
    for i, comp in enumerate(comps, 1):
        lines += format_component(comp, i if len(comps) > 1 else None)
    lines += [
        "---",
        AI_NOTE,
        "",
        f"_Generated {result.get('generated_at', '')} by Stack Scout from public data "
        "(GitHub, deps.dev, OSV, npm/PyPI/crates.io, Hacker News)._",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python tools/format_report.py result.json")
    sys.stdout.reconfigure(encoding="utf-8")
    print(format_report(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))))
