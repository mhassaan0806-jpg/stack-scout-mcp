# Stack Scout MCP: free open-source tool finder for Claude and Cursor

**The honest free-tool finder for your AI.** Describe what you want to build. Get free, open-source
tools for every part of it: checked to be alive, checked to be truly free, with the catch spelled out.

[![tests](https://github.com/mhassaan0806-jpg/stack-scout-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/mhassaan0806-jpg/stack-scout-mcp/actions/workflows/tests.yml)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Cost: free](https://img.shields.io/badge/cost-%240-brightgreen)

## What is Stack Scout? (in simple words)

You want to make an app. For example, a shoe shop.

Your app needs many parts:
- a page to log in
- a shopping cart
- a way to pay
- emails

You do not need to make every part yourself. People share free parts on the internet.
But it is hard to find good ones. Some are old. Some are broken. Some say "free", but they are not really free.

**Stack Scout helps your AI find the good free parts.**

1. You tell your AI (Claude or Cursor): "I want to make a shoe shop."
2. Your AI asks Stack Scout for help.
3. Stack Scout looks on GitHub. GitHub is a big website with free code.
4. Stack Scout checks every tool. Is it new? Do many people use it? Is it really free? Is there a catch?
5. Your AI gives you a short list: the best free tools, with links, good points and bad points.

Stack Scout is free. It runs on your computer. You do not pay for anything.

## How it works (for developers)

Stack Scout is an MCP server for AI assistants you already use (Claude, Cursor, ...). Your AI splits your
idea into needs. Stack Scout finds the tools for each need, reads their licenses and READMEs, checks
activity, downloads, security and community discussion, and hands your AI the facts. Your AI then
explains the pros, cons and the catch, without guessing from old training data.

## Why "honest"

AI assistants often recommend tools that are abandoned, archived, or "open source" in name only. Stack Scout
checks live data every time. Real examples from testing:

| Tool | GitHub says | Stack Scout found |
|---|---|---|
| Medusa (e-commerce) | License: "Other" | MIT core, but the Enterprise Edition needs a commercial agreement → **open core** |
| Meilisearch (search) | License: BUSL (not free) | MIT core, BUSL only for enterprise parts → **open core**, still usable for free |
| Terraform | License: BUSL | Restrictive → **not recommended** |
| Sentry | License: "Other" | Functional Source License, turns Apache only after 2 years → **not free today** |
| Elasticsearch | License: "Other" | You may choose AGPL → **free (copyleft)** |

It also skips archived repos, repos with no code changes in 2 years, and awesome-lists or tutorials
posing as tools.

## Example

```
> I want to build an online shoe store with TypeScript. Use Stack Scout.

## 1. Shopping cart & product catalog
| # | Tool            | Stars | Last code change | License                          | Score |
| 1 | bagisto/bagisto | 28.4k | 3 days ago       | MIT (free, permissive)           | 96    |
| 2 | saleor/saleor   | 23.6k | 1 day ago        | BSD-3-Clause (free, permissive)  | 95    |
| 3 | medusajs/medusa | 37.4k | today            | MIT (open core: some parts paid) | 91    |

#### medusajs/medusa: research notes
- README mentions paid terms: "The RBAC-based Enterprise Edition materials ... require a
  commercial agreement with MedusaJS, Inc."
- Activity: latest release v2.23.0 on 2026-11-20
- Adoption: package @medusajs/medusa on npm, 1.4M downloads last month
- Security practices (OpenSSF Scorecard): 5.7/10
- Known vulnerabilities in latest version: none listed in OSV
- README mentions (likely setup needs): Docker, PostgreSQL, Redis, Node.js
...
```

It works for anything, not just apps: "a 2D game engine" → Godot, PixiJS, GDevelop;
"extract text from PDF files in python" → pdfplumber, pdftext.

## Install

Requires Python 3.10+.

```bash
git clone https://github.com/mhassaan0806-jpg/stack-scout-mcp.git && cd stack-scout-mcp
python -m venv .venv
.venv/bin/pip install -r requirements.txt          # Windows: .venv\Scripts\pip install -r requirements.txt
```

Connect it to **Claude Code**:

```bash
claude mcp add stack-scout -- /full/path/.venv/bin/python /full/path/server.py
```

Or add it to **Claude Desktop** / **Cursor** config:

```json
{
  "mcpServers": {
    "stack-scout": {
      "command": "/full/path/.venv/bin/python",
      "args": ["/full/path/server.py"]
    }
  }
}
```

Optional: copy `.env.example` to `.env` and add a free GitHub token. It raises GitHub search from
10 to 30 a minute.

## Tools your AI gets

| Tool | Use it for |
|------|------------|
| `scout_stack` | Researched free tools for every need of a project |
| `find_tools` | One need ("send emails", "PDF invoices", "2D game engine") |
| `research_tool` | Vetting a GitHub link: maintained? truly free? what's the catch? |
| `plan_app_components` | Backup: guess an idea's needs from keywords |
| `list_building_blocks` | 24 common needs with tuned searches |

## Where the facts come from (all free, no paid keys)

GitHub (search, README, LICENSE, releases) · deps.dev (OpenSSF Scorecard, packages) · OSV
(vulnerabilities) · npm / PyPI / crates.io (downloads) · Hacker News (discussions).
Everything runs on your computer and the thinking is done by your own AI, so it costs $0 to run.

## Use it without an AI

```bash
python tools/scout_stack.py "online shoe store" --language TypeScript
python tools/scout_stack.py "pdf tool" --components "extract text from pdf files in python"
python tools/research_tool.py medusajs/medusa
```

## Tests

```bash
python -m unittest discover tests                 # offline, < 1 second
.venv/bin/python tests/live_mcp_smoke.py          # starts the MCP server like Claude does, live data
```

## How it's organised

```
server.py           MCP server: thin wrapper around tools/
tools/              Python scripts that do the work (search, license, health, research, rank, report)
tools/data/         Building-block catalog: add needs here, no code needed
workflows/          Plain-language guides: how to run, evaluate, connect and extend
tests/              Offline logic tests + a live MCP smoke test
.tmp/               Cache and scratch output (safe to delete)
```

## Limits (honestly)

- Ranking can't judge fit: a popular AI search engine may rank high for "site search". Your AI is told
  to judge fit and say "unknown" rather than guess.
- README checks are keyword hints ("read in context"), not legal advice.
- **Payments:** no open-source project makes card processing free. You'll get payment and billing
  platforms that still connect to a processor (Stripe, PayPal...) with per-transaction fees.
- No web search of its own yet. Your AI can web-search a pick further.

## Contributing

The easiest win is a better catalog. See [workflows/extend_catalog.md](workflows/extend_catalog.md).
Please run `python -m unittest discover tests` before opening a pull request.

## FAQ

**What is Stack Scout?**
Stack Scout is a free, open-source MCP server that helps AI assistants like Claude and Cursor find free,
open-source tools for any software project. It checks that each tool is maintained and truly free, and
explains the catch, such as paid "enterprise" features or license duties.

**Is Stack Scout free?**
Yes. It is MIT-licensed, runs on your own computer, uses your own AI assistant, and only calls free public
data sources. There is no account, subscription or API bill.

**What is an MCP server?**
MCP (Model Context Protocol) is a standard way to give AI assistants extra tools. An MCP server is a small
program the AI can call. Claude Desktop, Claude Code, Cursor, VS Code and other apps support MCP.

**How is this different from just asking an AI for free tools?**
An AI answering from memory can suggest tools that are abandoned, archived, or no longer open source.
Stack Scout checks live data every time: last code change, license file, releases, downloads, security
score and known vulnerabilities.

**Does it find open-source alternatives to paid software?**
Yes. Describe the need ("an open-source alternative to Shopify", "self-hosted analytics") and it returns
free, maintained options, with any paid parts flagged.

**Does it only work for web apps?**
No. It works for any need: games ("2D game engine"), data tools ("extract text from PDF files in python"),
mobile apps, internal tools and more.

**Which tools does it reject?**
Archived projects, projects with no code changes in two years, "source-available" licenses that restrict
use (BUSL, SSPL, Elastic, FSL), and awesome-lists or tutorials posing as tools.

## Keywords

free tool finder, open source alternatives, MCP server, Model Context Protocol, Claude MCP, Cursor MCP,
tech stack recommendation, open source software discovery, license checker, open core detection,
self-hosted alternatives, GitHub repository health, free developer tools, AI coding assistant tools

## License

[MIT](LICENSE)
