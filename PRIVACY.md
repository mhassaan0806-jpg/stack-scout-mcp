# Privacy

Stack Scout runs on your own computer. It has no server, no account and no analytics.
The project's authors receive nothing from it.

## What leaves your computer

To find and check tools, Stack Scout sends requests to these free public services:

| Service | What is sent | Why |
|---|---|---|
| GitHub (api.github.com, github.com, raw.githubusercontent.com) | Search words for your needs (e.g. "shopping cart"), names of repositories | Find tools, read READMEs, licenses and releases |
| deps.dev (Google) | Repository and package names | Security score, packages, known vulnerabilities |
| npm, PyPI stats, crates.io | Package names | Download counts |
| Hacker News search (Algolia) | Repository names and website addresses | Community discussions |

Requests use the user agent `stack-scout-mcp/<version>`. If you add a GitHub token, it is sent only to GitHub.
Each service's own privacy policy applies to what it receives.

## What is stored

Responses are cached on your computer to save time and rate limits:
`%LOCALAPPDATA%\stack-scout-mcp\cache` on Windows, `~/.cache/stack-scout-mcp/cache` on macOS/Linux
(or `.tmp/cache` when running from a clone). Delete the folder at any time.

Your idea and the AI's answers stay in your AI app. Stack Scout only receives the needs your AI passes to it.
