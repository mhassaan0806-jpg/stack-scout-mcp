"""Live smoke test: start server.py over stdio exactly like Claude/Cursor would, then call its tools.

Uses the network (GitHub search counts toward the 10/min free limit). Run with the venv Python:
    .venv\\Scripts\\python.exe tests\\live_mcp_smoke.py ["need to search"]
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent


async def main(need: str) -> None:
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")])
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = [t.name for t in (await session.list_tools()).tools]
        print("tools:", tools)
        assert {"scout_stack", "find_tools", "research_tool"} <= set(tools), tools

        start = time.time()
        result = await session.call_tool("find_tools", {"need": need, "top_n": 3})
        text = result.content[0].text
        print(f"\nfind_tools({need!r}) took {time.time() - start:.1f}s, is_error={result.is_error}\n")
        print(text)
        assert not result.is_error and "|" in text, "expected a results table"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main(" ".join(sys.argv[1:]) or "extract text from PDF files in python"))
