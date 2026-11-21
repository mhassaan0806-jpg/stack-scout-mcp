"""Stack Scout MCP server: the honest free-tool finder.

Gives an AI assistant (Claude, Cursor, ...) tools to find free, open-source tools for
anything a user wants to build, check that they are alive and truly free, and collect
the facts (paid parts, setup needs, adoption, security) to explain the catch honestly.

Runs on the user's own computer over stdio; the AI app starts it with
`uvx stack-scout-mcp` (installed) or `python server.py` (from a clone).
Setup: see workflows/connect_mcp_server.md
"""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from . import __version__
from .tools._common import FetchError, RateLimitError
from .tools.format_report import AI_NOTE, format_component, format_report, format_research
from .tools.github_search import get_repo
from .tools.plan_components import list_components, plan_components
from .tools.repo_health import assess
from .tools.research_tool import research as research_repo
from .tools.research_tool import resolve_license
from .tools.scout_stack import scout, scout_component

mcp = MCPServer(
    "stack-scout",
    version=__version__,
    website_url="https://github.com/mhassaan0806-jpg/stack-scout-mcp",
    instructions=(
        "Stack Scout finds free, open-source tools for anything a user wants to build, and checks they are "
        "alive and truly free. When a user describes a project or a need: (1) split it yourself into the "
        "separate needs it has, e.g. an online shoe store needs a product catalog and cart, payments, login, "
        "email; a PDF tool needs text extraction. (2) Call scout_stack with the idea and those needs as plain "
        "words or catalog ids (list_building_blocks). For a single need use find_tools; to vet a specific "
        "GitHub link use research_tool. (3) Write the answer from the returned facts only: for each need, a "
        "recommended pick and why it fits, pros, cons, the catch (paid or open-core parts, license duties, "
        "what it takes to host), and technical limits, with links. Say 'unknown' instead of guessing. If a "
        "well-known paid service is the usual choice, mention it briefly and label it paid. Users can ask "
        "you to web-search a tool further; do that with your own web search."
    ),
)


def _friendly_error(e: Exception) -> str:
    if isinstance(e, RateLimitError):
        return (f"Stack Scout hit GitHub's free rate limit: {e} Wait about a minute and try again "
                "(finished searches are cached), or add a free GITHUB_TOKEN to the .env file.")
    return f"Stack Scout could not reach a data source: {e}"


@mcp.tool()
def scout_stack(
    idea: str,
    needs: list[str] | None = None,
    language: str | None = None,
    top_n: int = 3,
    research: bool = True,
) -> str:
    """Find and research the best free, open-source tools for every need of a project.

    Args:
        idea: What the user wants to build, in plain words, e.g. "an online shoe store".
        needs: The separate needs you identified, as plain words ("extract text from PDFs",
            "shopping cart") or catalog ids ("auth", "payments"; see list_building_blocks).
            Strongly recommended. If omitted, needs are guessed from keywords in the idea.
        language: Preferred programming language for code libraries, e.g. "TypeScript".
            Self-hosted services (databases, search engines) are not filtered by language.
        top_n: Tools per need (1-5, default 3).
        research: Research each pick in depth (README, license, releases, downloads, security,
            Hacker News). Default true; set false for a quick list.

    Returns a Markdown report: per need, a ranked table plus research notes per tool.
    """
    try:
        result = scout(idea, needs, language, max(1, min(top_n, 5)), research=research)
    except (RateLimitError, FetchError) as e:
        return _friendly_error(e)
    return format_report(result)


@mcp.tool()
def find_tools(need: str, language: str | None = None, top_n: int = 3, research: bool = True) -> str:
    """Find and research free, open-source tools for ONE need, e.g. "send emails" or "PDF invoices".

    Args:
        need: Plain words or a catalog id (see list_building_blocks). A language named in the
            words ("...in python") is used as a filter.
        language: Preferred programming language for code libraries.
        top_n: How many tools to return (1-5, default 3).
        research: Research each pick in depth (default true).
    """
    try:
        result = scout(need, [need], language, max(1, min(top_n, 5)), research=research)
    except (RateLimitError, FetchError) as e:
        return _friendly_error(e)
    comp = result["components"][0]
    return "\n".join(format_component(comp) + ["---", AI_NOTE])


@mcp.tool()
def research_tool(repo: str) -> str:
    """Research one GitHub project in depth: is it maintained, truly free, what's the catch?

    Covers license (including open-core and restrictive terms read from the LICENSE file),
    paid or cloud mentions in the README, setup needs, latest release, downloads, OpenSSF
    security score, known vulnerabilities and Hacker News discussions.

    Args:
        repo: "owner/name" or a github.com URL.
    """
    try:
        data = resolve_license(get_repo(repo))
    except ValueError as e:
        return str(e)
    except (RateLimitError, FetchError) as e:
        return _friendly_error(e)
    health = assess(data)
    verdict = {"ok": "Looks good", "caution": "Usable, with caveats", "rejected": "Not recommended"}[health["status"]]
    entry = {**data, "health": health, "research": research_repo(data)}
    lines = [f"## {data['full_name']}: {verdict}", "", f"{data['description']} ({data['url']}). Score {health['score']}/100.", ""]
    lines += [f"- **Not recommended because:** {r}" for r in health["rejected_because"]]
    lines += format_research(entry)[2:]  # skip its own heading
    lines += ["---", AI_NOTE]
    return "\n".join(lines)


@mcp.tool()
def plan_app_components(idea: str) -> str:
    """Backup only: guess an idea's needs from keywords. Prefer splitting the idea yourself."""
    plan = plan_components(idea)
    lines = [f"Building blocks for: {idea}"]
    if plan["archetypes"]:
        lines.append(f"Looks like: {', '.join(plan['archetypes'])}")
    lines += [f"- {c['id']}: {c['name']}. Why: {c['why']}" for c in plan["components"]]
    lines.append("\nReview this, add what's missing in plain words, and pass the list to scout_stack as `needs`.")
    return "\n".join(lines)


@mcp.tool()
def list_building_blocks() -> str:
    """List the catalog ids with tuned GitHub searches. Any other need can be passed as plain words."""
    return "\n".join(f"- {c['id']}: {c['name']}" for c in list_components())


def main() -> None:
    """Console entry point (`stack-scout-mcp`): serve over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
