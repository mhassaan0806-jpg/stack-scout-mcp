# Workflow: Add or tune a building block

## Objective
Teach Stack Scout a new building block (e.g. "PDF generation") or fix one whose results are poor,
by editing `stack_scout_mcp/tools/data/components.json`. No code changes needed.

## Required inputs
- The block's purpose in plain words
- A GitHub topic that real projects for it use (browse `https://github.com/topics/<name>`)

## Steps
1. Find the best query. Try 2-3 candidates and compare the top results:
   ```
   python -m stack_scout_mcp.tools.github_search "topic:pdf-generation" --limit 8
   python -m stack_scout_mcp.tools.github_search "topic:pdf" --limit 8
   ```
   Prefer `topic:` queries. Plain words match descriptions loosely and pull in noise.
   Each try is one GitHub search (10/min without a token).
2. Add an entry under `components`:
   ```json
   "pdf": {"name": "PDF generation", "query": "topic:pdf-generation", "language_sensitive": true,
           "keywords": ["pdf", "invoice pdf", "export pdf", "printable"]}
   ```
   - `language_sensitive`: `true` for code libraries you import, `false` for services you run beside your app.
   - `keywords`: words a user would say in their idea. They are matched as whole words, case-insensitive.
3. Optional: add the id to any `archetypes` that usually need it.
4. Verify:
   ```
   python -m stack_scout_mcp.tools.plan_components "an invoicing app that exports PDF invoices"
   python -m stack_scout_mcp.tools.scout_stack "invoicing app" --components pdf
   ```
5. Note the query you chose and why in the learnings log below.

## Edge cases
- A topic with only a few repos: add `language_sensitive: false` or pick a broader topic so the
  block doesn't return nothing.
- Too many tutorials or lists: extend `_NOT_A_TOOL` in `stack_scout_mcp/tools/repo_health.py` instead of fighting it in the query.

## Learnings log
- 2026-11-22: initial 24 blocks; every query checked live against GitHub search.
- Chosen after comparing alternatives:
  - `notifications`: `topic:push-notifications` (novu, ntfy, apprise). `topic:notifications` pulled in huginn and changedetection.
  - `i18n`: `topic:i18n topic:localization` (formatjs, weblate, lingui, tolgee). `topic:i18n` alone returned admin templates.
  - `forms`: `topic:forms`, made language-sensitive (react-hook-form, formik, formbricks).
    `topic:form-builder` pulled in cakephp and ONLYOFFICE; `topic:survey` pulled in research paper lists.
  - `scheduling`: `topic:appointment-scheduling` (thunderbird/appointment, tymeslot). Small but on target;
    `topic:scheduling` returns job schedulers (luigi, apscheduler).
- Known gaps: Cal.com (best-known free booking tool) isn't reached by any topic tried
  (`calendly`, `booking-system`, `scheduling self-hosted`). `database` (`topic:database`) mixes app
  databases with DB clients and monitoring tools. Combining it with `topic:postgresql` didn't help.
  The user's AI should add judgement for these two blocks.
