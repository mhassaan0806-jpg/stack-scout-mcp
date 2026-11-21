# Workflow: Evaluate a single repo

## Objective
Decide if one GitHub project is safe to build on: alive, used, truly free, and what the catch is.
Use when the user pastes a link, or to double-check a pick before recommending it.

## Required inputs
- `owner/name` or a github.com URL.

## Tools
```
python tools/research_tool.py medusajs/medusa          # full research notes
python tools/repo_health.py medusajs/medusa saleor/saleor   # quick health + score (GitHub label only)
python tools/license_check.py MIT AGPL-3.0 BUSL-1.1       # what a license means
```
Through MCP: `research_tool("medusajs/medusa")`.

## Hard rejects (status `rejected`, never recommended)
| Rule | Why |
|------|-----|
| Name looks like awesome-list, tutorial, guide, course, examples | Reading material, not a tool |
| Archived on GitHub | Owner has stopped maintaining it |
| No code pushed in 730+ days | Probably abandoned; security fixes unlikely |
| Only a restrictive license: BUSL, SSPL, Elastic, FSL, Commons Clause, CC-BY-NC, PolyForm | Source-available, not free to use commercially |

## License reading (license_check.classify_text)
GitHub's label is a starting point. The LICENSE file decides:
| What the file says | Result |
|---|---|
| Free license only (MIT, Apache, BSD...) | That license's category |
| Free license + "enterprise edition" / `ee/` folder / commercial license | **open core**: listed with a warning |
| Free license + restrictive license for *some parts* (Meilisearch: MIT + BUSL EE) | **open core** |
| A choice that includes a free option (Elasticsearch: AGPL or SSPL or Elastic) | The free option, with a note |
| Restrictive license that turns free later (Sentry FSL, BUSL "Change License") | **not free**, note says when it converts |
| Nothing recognised | unknown: "read it before using" warning |

## Score (0-100)
- **Popularity, 0-40**: `8 × log10(stars + 1)`: 100★ ≈ 16, 1k ≈ 24, 10k ≈ 32, 100k = 40
- **Recency, 0-40**: last push ≤ 90 days 40 · ≤ 180 32 · ≤ 365 22 · ≤ 730 10
- **License, 0-20**: permissive 20 · weak copyleft 15 · open core 14 · copyleft 8 · unknown 0

Ranking adds relevance: up to 15 for GitHub's best-match order (catalog needs), or up to 25 for the
share of the user's key words the repo mentions (plain-language needs).

## Research notes (research_tool.py), all free and none using the GitHub API quota
| Fact | Source |
|---|---|
| Paid / cloud / enterprise mentions, setup needs (Docker, Postgres...), maturity flags (beta...) | README via raw.githubusercontent.com |
| Latest release and date | github.com/<repo>/releases.atom |
| Security practices (OpenSSF Scorecard 0-10, weak checks) | deps.dev |
| Main package, monthly downloads | deps.dev + npm / PyPI (pypistats) / crates.io |
| Known vulnerabilities in the latest version | OSV via deps.dev |
| Community discussion | Hacker News (Algolia API), stories naming the tool ranked first |

## Manual checks the tools can't do
- Is the free edition really usable, or a teaser for the paid cloud? (Read what the paid mentions refer to.)
- Can a beginner host it? (Docker one-liner, free managed tier?)
- Are recent bug reports answered?

## Learnings log
- 2026-11-22: OpenSSF Scorecard is often 4-6/10 even for popular, well-run projects, because checks like
  Fuzzing, SAST and CII-Best-Practices are rarely done. Present it as "security practices", not "is it safe".
- 2026-11-22: README keyword matches are noisy ("pricing" inside a feature list), so lines with
  enterprise / paid / commercial / proprietary are shown first.
