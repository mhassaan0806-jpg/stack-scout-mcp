# Workflow: Scout free tools for anything someone wants to build

## Objective
Turn any request ("an online shoe store", "a 2D game engine", "extract text from PDFs in Python")
into free, open-source, maintained tools for each need, plus the honest facts behind each pick:
what's free and what's paid, the catch, what it takes to host, adoption and security.
Stack Scout collects facts. The user's AI writes the pros, cons and fit from them.

## Required inputs
- **Idea** (required): what the user wants to build, in their words.
- **Needs** (strongly recommended): the separate needs, split by the user's AI. Each one is a catalog
  id (`auth`, `payments`... see `python -m stack_scout_mcp.tools.plan_components --list`) or plain words.
- **Language** (optional): preferred language for code libraries.
- **Top N** (optional, default 3) and **research** (default on).

## Flow and tools
1. **Split into needs.** Normally the user's AI does this. Backup: `stack_scout_mcp/tools/plan_components.py`
   (keyword rules). A request that matches nothing is searched as typed; app-like requests also get
   common app blocks.
2. **Search** (`stack_scout_mcp/tools/scout_stack.py` → `github_search.py`), one need at a time (rate limited):
   - catalog need: one tuned `topic:` query from `stack_scout_mcp/tools/data/components.json`
   - plain words: filler removed and any named language pulled out ("in python" → `language:Python`).
     Then two searches, merged: all key words (precise) and the nouns only (broad).
3. **License check** (`research_tool.resolve_license` → `license_check.classify_text`): reads the
   LICENSE file for anything GitHub labels "Other" or non-free, and for every pick. That catches
   open core hidden behind an "MIT" label.
4. **Filter and rank** (`rank_tools.py` → `repo_health.py`): see `workflows/evaluate_repo.md`.
5. **Research every pick, in parallel** (`research_tool.py`): README (paid/cloud mentions, setup needs,
   maturity flags), latest release, OpenSSF Scorecard, main package + downloads, known vulnerabilities
   (OSV), Hacker News discussions. None of this uses the GitHub API quota.
6. **Report** (`format_report.py`): a table per need, research notes per pick, and a closing note
   telling the AI how to present it honestly.

```
python -m stack_scout_mcp.tools.scout_stack "online shoe store" --components ecommerce,payments,auth --language TypeScript --out .tmp/shoe.md
python -m stack_scout_mcp.tools.scout_stack "pdf tool" --components "extract text from pdf files in python"
python -m stack_scout_mcp.tools.research_tool medusajs/medusa
```
Through MCP: `scout_stack(idea, needs, language)`, `find_tools(need)`, `research_tool(repo)`.

## Expected output
Markdown. Per need: a ranked table (link, description, stars, last code change, license with
category, score), skipped repos with reasons, then research notes per pick. Ends with the "For the AI
presenting this" note. Typical timings: one need 3-20s, a 9-need app about 45s.

## Edge cases and known limits
- **Rate limits.** Without a token GitHub allows 10 searches a minute. A catalog need costs 1 search and a
  plain-words need costs 2 (3 if a language filter leaves too few). Searches stop at the first rate-limit
  error and the remaining needs are marked "Not searched". Cached results (`.tmp/cache/`, 6h for search,
  24h for research) make a re-run cheap. Fix: wait 60s, or add a free `GITHUB_TOKEN`.
- **Payments.** No open-source tool makes card processing free. Results are payment orchestration and
  billing tools that still connect to a processor (Stripe, PayPal...) with per-transaction fees.
- **Relevance is the AI's job.** Ranking favours healthy, popular repos that mention the search words.
  It can't tell that an AI search engine is a poor fit for an online store's product search. The user's
  AI must judge fit, which is why the report says so.
- **README signals are hints.** "Paid mentions" and "setup needs" come from keyword matching. The report
  says "read in context" and the AI should check the linked README before stating them as fact.
- **No web search of our own.** DuckDuckGo blocks automated clients, and we don't disguise ours.
  The user's AI can web-search a pick further with its own tools.

## Learnings log
- 2026-11-22: `topic:` queries beat plain keywords by a wide margin for catalog needs.
- 2026-11-22: Broad topics pull in tutorials and lists, so `repo_health.py` rejects awesome-*, *-tutorial etc.
- 2026-11-22: DuckDuckGo HTML search returns a bot check, so `web_search.py` was removed.
  Options for later: a free search API with the user's own key (Brave), or self-hosted SearXNG.
- 2026-11-22: GitHub's license label is unreliable for open core: Medusa = "Other", PostHog = "Other",
  Meilisearch = "BUSL" (really MIT core + BUSL enterprise). Reading LICENSE text fixes all three.
  Checked against 8 real repos (terraform, meilisearch, posthog, medusa, umami, elasticsearch, sentry, plausible).
- 2026-11-22: Plain-word searches failed when every word had to match ("extract text pdf files" missed the
  big libraries). Dropping filler and adding a nouns-only search fixed it: pdfplumber now ranks first.
- 2026-11-22: deps.dev's package list is cut short for big monorepos (Medusa: 1,500 versions, wrong package
  picked). `main_package` now tries `<repo>` and `@<owner>/<repo>` directly and checks they come from the repo.
