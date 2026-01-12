# Refactoring Plan: Migrate to agent-browser

## Executive Summary

This document outlines the plan to refactor the LlmAgentBrowser project to use Vercel Labs' `agent-browser` package as an alternative browser automation approach alongside the existing Browser MCP and Chrome DevTools MCP implementations.

---

## 1. Current Architecture vs agent-browser

### Current Implementation (Browser MCP)

```
┌─────────────────┐     MCP Protocol      ┌─────────────────┐
│   LLM Client    │◄────────────────────►│  MCP Server     │
│(Gemini/Claude/  │      (stdio)         │(@browsermcp/mcp)│
│ OpenAI)         │                       └────────┬────────┘
└─────────────────┘                                │
                                          Chrome Extension API
                                                   │
                                          ┌────────▼────────┐
                                          │ Running Chrome  │
                                          │(existing logins)│
                                          └─────────────────┘
```

**Characteristics:**
- MCP protocol for communication
- Chrome Extension-based
- Works with existing browser session (no Chrome close required)
- 12 browser tools via MCP

### agent-browser Architecture

```
┌─────────────────┐                       ┌─────────────────┐
│   LLM Client    │──subprocess/shell───►│ agent-browser   │
│(Gemini/Claude/  │    (CLI calls)       │  (Rust CLI)     │
│ OpenAI)         │                       └────────┬────────┘
└─────────────────┘                                │
                                          ┌────────▼────────┐
                                          │ Node.js Daemon  │
                                          │ (BrowserManager)│
                                          └────────┬────────┘
                                                   │
                                          ┌────────▼────────┘
                                          │ Playwright      │
                                          │ (Chromium)      │
                                          └─────────────────┘
```

**Characteristics:**
- CLI-based invocation (subprocess calls)
- Rust CLI + Node.js daemon architecture
- Playwright-powered (Chromium download required)
- Ref-based element selection (@e1, @e2) - optimal for LLMs
- Session isolation for parallel automation
- 100+ available actions

---

## 2. Key Differences & Trade-offs

| Feature | Browser MCP (Current) | agent-browser (New) |
|---------|----------------------|---------------------|
| **Browser** | Existing Chrome | Fresh Chromium (Playwright) |
| **Login Sessions** | Preserved | Requires restoration or login flow |
| **Communication** | MCP Protocol | CLI subprocess |
| **Element Selection** | CSS selectors | Ref-based (@e1) from snapshots |
| **Parallelism** | Single browser | Session isolation |
| **Headless** | N/A (uses existing) | Yes (default), headed optional |
| **Setup** | Chrome extension | npm install + chromium download |
| **Bot Detection** | Low (real browser) | Higher (detectable as automation) |

### agent-browser Advantages
1. **Ref-based selection**: Eliminates complex CSS selector construction
2. **Session isolation**: Run multiple independent browser instances
3. **Faster execution**: Rust CLI + persistent daemon
4. **More actions**: 100+ available commands
5. **No extension dependency**: Self-contained

### agent-browser Disadvantages
1. **Fresh browser**: No existing login sessions
2. **Bot detection**: Playwright-launched browser may trigger detection
3. **Chromium download**: ~200MB download required
4. **Twitter/X login**: Will need credentials or session restoration

---

## 3. Proposed Implementation

### 3.1 New File Structure

```
LlmAgentBrowser/
├── twitter_fetcher_browsermcp.py      # Existing: Browser MCP approach
├── twitter_fetcher_mcp.py             # Existing: Chrome DevTools MCP
├── twitter_tweet_fetcher.py           # Existing: browser-use approach
├── twitter_fetcher_agentbrowser.py    # NEW: agent-browser approach
├── agent_browser_client.py            # NEW: Python wrapper for agent-browser CLI
└── ...
```

### 3.2 Core Components

#### 3.2.1 AgentBrowserClient Class

```python
class AgentBrowserClient:
    """Python wrapper for agent-browser CLI commands."""

    def __init__(self, session: str = "default", headed: bool = False):
        self.session = session
        self.headed = headed
        self._ensure_installed()

    async def open(self, url: str) -> dict:
        """Navigate to URL."""
        return await self._run_command("open", url)

    async def snapshot(self, interactive: bool = True, compact: bool = True) -> dict:
        """Get accessibility tree with element refs."""
        args = []
        if interactive:
            args.append("-i")
        if compact:
            args.append("-c")
        return await self._run_command("snapshot", *args)

    async def click(self, ref: str) -> dict:
        """Click element by ref (@e1) or selector."""
        return await self._run_command("click", ref)

    async def type(self, ref: str, text: str) -> dict:
        """Type text into element."""
        return await self._run_command("type", ref, text)

    async def fill(self, ref: str, text: str) -> dict:
        """Fill input field (clears first)."""
        return await self._run_command("fill", ref, text)

    async def press(self, key: str) -> dict:
        """Press keyboard key."""
        return await self._run_command("press", key)

    async def scroll(self, direction: str = "down", amount: int = 500) -> dict:
        """Scroll page."""
        return await self._run_command("scroll", direction, str(amount))

    async def wait(self, selector_or_ms: str) -> dict:
        """Wait for element or milliseconds."""
        return await self._run_command("wait", selector_or_ms)

    async def evaluate(self, script: str) -> dict:
        """Execute JavaScript and return result."""
        return await self._run_command("evaluate", script)

    async def screenshot(self, path: str = None) -> dict:
        """Take screenshot."""
        args = []
        if path:
            args.extend(["--path", path])
        return await self._run_command("screenshot", *args)

    async def get_text(self, ref: str = None) -> dict:
        """Get text content."""
        args = ["text"]
        if ref:
            args.append(ref)
        return await self._run_command("get", *args)

    async def close(self) -> dict:
        """Close browser."""
        return await self._run_command("close")

    async def _run_command(self, *args) -> dict:
        """Execute agent-browser CLI command."""
        cmd = ["agent-browser", "--session", self.session, "--json"]
        if self.headed:
            cmd.append("--headed")
        cmd.extend(args)

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"Command failed: {stderr.decode()}")

        return json.loads(stdout.decode()) if stdout else {}
```

#### 3.2.2 AgentBrowserOrchestrator Class

```python
class AgentBrowserOrchestrator:
    """LLM orchestrator using agent-browser tools."""

    def __init__(self, model_type: str, browser_client: AgentBrowserClient):
        self.model_type = model_type
        self.browser = browser_client
        self.tool_calls_count = 0

    def get_tools(self) -> list[dict]:
        """Return tool definitions for LLM function calling."""
        return [
            {
                "name": "browser_open",
                "description": "Navigate to a URL",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to navigate to"}
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "browser_snapshot",
                "description": "Get accessibility tree with element refs (@e1, @e2, etc.) for clicking/typing. Use -i for interactive elements only.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "interactive": {"type": "boolean", "description": "Only return interactive elements", "default": True}
                    }
                }
            },
            {
                "name": "browser_click",
                "description": "Click an element by its ref (e.g., @e1) from snapshot",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ref": {"type": "string", "description": "Element ref like @e1 or CSS selector"}
                    },
                    "required": ["ref"]
                }
            },
            {
                "name": "browser_type",
                "description": "Type text into an element",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ref": {"type": "string", "description": "Element ref or selector"},
                        "text": {"type": "string", "description": "Text to type"}
                    },
                    "required": ["ref", "text"]
                }
            },
            {
                "name": "browser_scroll",
                "description": "Scroll the page",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "direction": {"type": "string", "enum": ["up", "down"], "default": "down"},
                        "amount": {"type": "integer", "description": "Pixels to scroll", "default": 500}
                    }
                }
            },
            {
                "name": "browser_press",
                "description": "Press a keyboard key (Enter, Tab, Escape, PageDown, etc.)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Key to press"}
                    },
                    "required": ["key"]
                }
            },
            {
                "name": "browser_wait",
                "description": "Wait for element or duration (milliseconds)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string", "description": "CSS selector or milliseconds (e.g., '2000')"}
                    },
                    "required": ["target"]
                }
            },
            {
                "name": "browser_evaluate",
                "description": "Execute JavaScript code and return the result",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "script": {"type": "string", "description": "JavaScript code to execute"}
                    },
                    "required": ["script"]
                }
            },
            {
                "name": "browser_get_text",
                "description": "Get text content from page or element",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ref": {"type": "string", "description": "Optional element ref to get text from"}
                    }
                }
            }
        ]

    async def execute_tool(self, name: str, args: dict) -> str:
        """Execute a browser tool and return result."""
        self.tool_calls_count += 1

        try:
            if name == "browser_open":
                result = await self.browser.open(args["url"])
            elif name == "browser_snapshot":
                result = await self.browser.snapshot(args.get("interactive", True))
            elif name == "browser_click":
                result = await self.browser.click(args["ref"])
            elif name == "browser_type":
                result = await self.browser.type(args["ref"], args["text"])
            elif name == "browser_scroll":
                result = await self.browser.scroll(args.get("direction", "down"), args.get("amount", 500))
            elif name == "browser_press":
                result = await self.browser.press(args["key"])
            elif name == "browser_wait":
                result = await self.browser.wait(args["target"])
            elif name == "browser_evaluate":
                result = await self.browser.evaluate(args["script"])
            elif name == "browser_get_text":
                result = await self.browser.get_text(args.get("ref"))
            else:
                return f"Unknown tool: {name}"

            return json.dumps(result, indent=2) if isinstance(result, dict) else str(result)
        except Exception as e:
            return f"Error: {str(e)}"
```

### 3.3 Main Fetcher Implementation

```python
# twitter_fetcher_agentbrowser.py

async def fetch_tweets_with_agentbrowser(
    model_type: str,
    num_tweets: int = 5,
    num_scrolls: int = 3,
    headed: bool = False
) -> ModelResult:
    """Fetch tweets using agent-browser + LLM."""

    browser = AgentBrowserClient(session="twitter", headed=headed)
    orchestrator = AgentBrowserOrchestrator(model_type, browser)

    js_code = get_tweet_extraction_js(num_tweets)

    task = f"""You are a browser automation agent using agent-browser tools.

WORKFLOW:
1. Use browser_open to navigate to "https://x.com"
2. Use browser_wait with "3000" to wait for page load
3. Use browser_snapshot to see the page (returns refs like @e1, @e2)
4. If login is required, identify login fields from snapshot and fill them
5. Once on the timeline, scroll down {num_scrolls} times:
   - Use browser_press with "PageDown"
   - Use browser_wait with "2000" after each scroll
6. Use browser_evaluate to run this JavaScript and extract tweets:

{js_code}

IMPORTANT:
- Use refs from browser_snapshot (e.g., @e1) to click/type
- After navigation or clicks, always take a new snapshot
- The snapshot shows interactive elements with their refs
- Return the extracted tweets as JSON

Return the JSON array of tweets when done.
"""

    raw_output = await orchestrator.run_task(task, max_steps=30)
    # ... process results
```

---

## 4. Implementation Steps

### Phase 1: Setup & Infrastructure
- [ ] Install agent-browser globally: `npm install -g agent-browser`
- [ ] Download Chromium: `agent-browser install`
- [ ] Create `agent_browser_client.py` with Python CLI wrapper
- [ ] Add tests for basic commands (open, snapshot, click)

### Phase 2: Core Implementation
- [ ] Create `AgentBrowserOrchestrator` class
- [ ] Implement tool definitions for LLM function calling
- [ ] Create tool execution logic with error handling
- [ ] Implement LLM adapters (Gemini, Claude, OpenAI)

### Phase 3: Twitter Fetcher
- [ ] Create `twitter_fetcher_agentbrowser.py`
- [ ] Handle login flow (if required)
- [ ] Implement scroll and extraction logic
- [ ] Parse and format tweet output

### Phase 4: Integration & Testing
- [ ] Add Makefile targets for agent-browser approach
- [ ] Update README with new approach documentation
- [ ] Run comparison benchmarks with other approaches
- [ ] Update design.md with agent-browser architecture

---

## 5. Makefile Additions

```makefile
# agent-browser targets
ab-install:
	npm install -g agent-browser
	agent-browser install

ab-claude:
	uv run python twitter_fetcher_agentbrowser.py --model claude --tweets $(TWEETS)

ab-gemini:
	uv run python twitter_fetcher_agentbrowser.py --model gemini --tweets $(TWEETS)

ab-openai:
	uv run python twitter_fetcher_agentbrowser.py --model openai --tweets $(TWEETS)

ab-all:
	uv run python twitter_fetcher_agentbrowser.py --all --tweets $(TWEETS)

ab-headed:
	uv run python twitter_fetcher_agentbrowser.py --model claude --tweets $(TWEETS) --headed
```

---

## 6. Handling Twitter Login

Since agent-browser uses a fresh browser instance, we need to handle authentication:

### Option A: Session State Restoration
```python
# Save storage state after manual login
await browser.evaluate("/* login flow */")
# Then: agent-browser storage_save twitter_session.json

# Restore in future runs
# agent-browser storage_load twitter_session.json
```

### Option B: Environment-Based Login
```python
async def handle_twitter_login(orchestrator):
    """Automated login using environment credentials."""
    username = os.getenv("TWITTER_USERNAME")
    password = os.getenv("TWITTER_PASSWORD")

    if not username or not password:
        raise ValueError("TWITTER_USERNAME and TWITTER_PASSWORD required")

    # LLM handles login flow with credentials
    login_task = f"""
    Login to Twitter/X:
    1. Navigate to https://x.com/login
    2. Use browser_snapshot to find the username field
    3. Type username: {username}
    4. Click next/continue
    5. Type password: {password}
    6. Submit login
    7. Wait for timeline to load
    """
```

### Option C: Headed Mode for Manual Login (Development)
```bash
# Run in headed mode, manually login, then continue
make ab-headed
```

---

## 7. Expected Benefits

1. **Better LLM Integration**: Ref-based selection eliminates need for complex CSS selectors
2. **More Actions**: 100+ commands vs 12 in Browser MCP
3. **Session Isolation**: Can run multiple browsers in parallel
4. **Faster Execution**: Rust CLI + persistent daemon
5. **Self-Contained**: No browser extension dependency

---

## 8. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Bot detection on Twitter | Use headed mode, add delays, consider session restoration |
| CLI subprocess overhead | Batch commands, use session persistence |
| Chromium download size | One-time setup, document in README |
| Login complexity | Provide session save/restore, env-based login option |

---

## 9. Success Criteria

- [ ] Successfully fetch tweets from Twitter/X using agent-browser
- [ ] Support all three LLM providers (Gemini, Claude, OpenAI)
- [ ] Comparable or better performance vs Browser MCP
- [ ] Documented setup and usage in README
- [ ] Makefile targets for easy execution
- [ ] Comparison table updated with new approach

---

## 10. Timeline Estimate

This plan can be implemented in the following phases:
- Phase 1 (Setup): Infrastructure and basic wrapper
- Phase 2 (Core): Orchestrator and LLM integration
- Phase 3 (Fetcher): Twitter-specific implementation
- Phase 4 (Polish): Documentation and testing

---

## Appendix: agent-browser Command Reference

```bash
# Navigation
agent-browser open <url>
agent-browser back
agent-browser forward
agent-browser reload

# Interaction
agent-browser click <ref|selector>
agent-browser type <ref|selector> <text>
agent-browser fill <ref|selector> <text>
agent-browser press <key>
agent-browser scroll [up|down] [amount]

# State
agent-browser snapshot [-i interactive] [-c compact]
agent-browser screenshot [--path file.png]
agent-browser get text|html|value [selector]

# JavaScript
agent-browser evaluate <script>

# Session
agent-browser --session <name> <command>
agent-browser cookies [get|set|clear]
agent-browser storage [get|set|clear]

# Options
--json          # JSON output
--headed        # Show browser window
--debug         # Debug output
```
