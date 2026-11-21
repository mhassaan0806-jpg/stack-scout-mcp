# Workflow: Install, run and connect the MCP server

## Objective
Get Stack Scout running on a computer and plugged into an AI assistant (Claude Code,
Claude Desktop, Cursor), then confirm it works.

## Required inputs
- Python 3.10+
- Absolute path to this folder (below: `<PROJECT>`)

## Steps
1. Install the only dependency, ideally in a virtual environment:
   ```
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt        # Windows
   .venv/bin/pip install -r requirements.txt            # macOS / Linux
   ```
2. Optional: copy `.env.example` to `.env` and add a free `GITHUB_TOKEN`.
3. Connect it to an assistant. Use the venv's Python so `mcp` is found.

   **Claude Code**
   ```
   claude mcp add stack-scout -- "<PROJECT>\.venv\Scripts\python.exe" "<PROJECT>\server.py"
   ```

   **Claude Desktop** (`claude_desktop_config.json`), or **Cursor** (`~/.cursor/mcp.json`):
   ```json
   {
     "mcpServers": {
       "stack-scout": {
         "command": "<PROJECT>\\.venv\\Scripts\\python.exe",
         "args": ["<PROJECT>\\server.py"]
       }
     }
   }
   ```
   Restart the app after editing its config.
4. Test in the assistant: "I want to build an online shoe store. Use Stack Scout to find free tools."
   You should get a report with tables for cart, payments, login and other blocks.

## MCP tools exposed
| Tool | What it does |
|------|--------------|
| `scout_stack(idea, needs?, language?, top_n?, research?)` | Researched report for every need of a project |
| `find_tools(need, language?, top_n?, research?)` | Researched report for one need |
| `research_tool(repo)` | Deep check of one GitHub repo: free? alive? what's the catch? |
| `plan_app_components(idea)` | Backup keyword guess of an idea's needs |
| `list_building_blocks()` | Catalog ids with tuned searches |

## Test it
```
python -m unittest discover tests                    # offline logic tests, no network, < 1s
.venv\Scripts\python.exe tests\live_mcp_smoke.py     # starts server.py over stdio like Claude does
.venv\Scripts\python.exe tests\live_mcp_smoke.py "2d game engine"
```

## Edge cases
- **Server doesn't show up:** the Python path in the config is usually wrong or the venv lacks `mcp`.
  Run `<PROJECT>\.venv\Scripts\python.exe server.py` by hand. It should sit waiting for input
  (that's normal for stdio). Press Ctrl+C to exit.
- **Never `print()` inside tools** called by the server: stdout is the MCP channel and stray output
  corrupts it. Return strings instead.
- **Rate-limit replies:** expected with no token after several runs in a minute. See `scout_stack.md`.

## Learnings log
- 2026-11-22: MCP Python SDK 2.x renamed `FastMCP` to `MCPServer` (`from mcp.server.mcpserver import MCPServer`).
  requirements.txt pins `mcp>=2.0,<3`.
- 2026-11-22: A 9-need report takes about 45s. Research runs in parallel after all searches, so this stays well
  under typical client tool timeouts. If a client times out, call with `research: false` or fewer needs.
