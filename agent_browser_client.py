"""
Agent Browser Client - Python wrapper for agent-browser CLI

This module provides a Python interface to the agent-browser CLI tool from Vercel Labs.
agent-browser is a headless browser automation tool designed for AI agents, featuring:
- Ref-based element selection (@e1, @e2) from accessibility snapshots
- Session isolation for parallel automation
- Rust CLI + Node.js daemon architecture
- 100+ browser automation commands

Installation:
    npm install -g agent-browser
    agent-browser install  # Downloads Chromium

Usage:
    from agent_browser_client import AgentBrowserClient

    # Basic usage (fresh Chromium instance)
    async with AgentBrowserClient(session="my-session") as browser:
        await browser.open("https://example.com")
        snapshot = await browser.snapshot(interactive=True)
        await browser.click("@e1")

    # Use installed Chrome with existing profile
    async with AgentBrowserClient(
        session="my-session",
        executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        user_data_dir="~/Library/Application Support/Google/Chrome",
        headed=True
    ) as browser:
        await browser.open("https://x.com")  # Already logged in!

    # Connect to existing Chrome via CDP (Chrome DevTools Protocol)
    # First start Chrome with: chrome --remote-debugging-port=9222
    async with AgentBrowserClient(
        session="my-session",
        cdp_url="http://localhost:9222"
    ) as browser:
        await browser.open("https://x.com")
"""

import asyncio
import json
import os
import shutil
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class CommandResult:
    """Result from an agent-browser command."""
    success: bool
    data: Any
    error: Optional[str] = None
    raw_output: str = ""


class AgentBrowserClient:
    """
    Python client for agent-browser CLI.

    Provides async methods for browser automation commands that map to
    agent-browser CLI commands executed via subprocess.

    Attributes:
        session: Session name for browser isolation
        headed: Whether to show browser window (default: headless)
        debug: Enable debug output
        timeout: Default command timeout in seconds
        executable_path: Path to Chrome/Chromium executable (uses default profile)
        user_data_dir: Path to Chrome user data directory for profile persistence
        cdp_url: Connect to existing Chrome via CDP (e.g., http://localhost:9222)
    """

    def __init__(
        self,
        session: str = "default",
        headed: bool = False,
        debug: bool = False,
        timeout: float = 30.0,
        executable_path: Optional[str] = None,
        user_data_dir: Optional[str] = None,
        cdp_url: Optional[str] = None
    ):
        self.session = session
        self.headed = headed
        self.debug = debug
        self.timeout = timeout
        self.executable_path = executable_path
        self.user_data_dir = user_data_dir
        self.cdp_url = cdp_url
        self._verified = False

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_installed()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - close browser."""
        try:
            await self.close()
        except Exception:
            pass  # Ignore errors on cleanup

    async def _ensure_installed(self) -> None:
        """Verify agent-browser is installed."""
        if self._verified:
            return

        if not shutil.which("agent-browser"):
            raise RuntimeError(
                "agent-browser is not installed. Install with:\n"
                "  npm install -g agent-browser\n"
                "  agent-browser install"
            )
        self._verified = True

    async def _run_command(self, *args: str, timeout: Optional[float] = None) -> CommandResult:
        """
        Execute an agent-browser CLI command.

        Args:
            *args: Command arguments (e.g., "open", "https://example.com")
            timeout: Command timeout in seconds (overrides default)

        Returns:
            CommandResult with success status, data, and any errors
        """
        await self._ensure_installed()

        cmd = ["agent-browser", "--session", self.session, "--json"]
        if self.headed:
            cmd.append("--headed")
        if self.debug:
            cmd.append("--debug")
        if self.executable_path:
            cmd.extend(["--executable-path", self.executable_path])
        cmd.extend(args)

        effective_timeout = timeout or self.timeout

        # Set environment variables for options not directly supported by CLI
        env = os.environ.copy()
        if self.executable_path:
            env["AGENT_BROWSER_EXECUTABLE_PATH"] = self.executable_path
        if self.user_data_dir:
            # Expand ~ to home directory
            expanded_path = os.path.expanduser(self.user_data_dir)
            env["AGENT_BROWSER_USER_DATA_DIR"] = expanded_path
        if self.cdp_url:
            env["AGENT_BROWSER_CDP_URL"] = self.cdp_url

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=effective_timeout
            )

            stdout_str = stdout.decode("utf-8").strip() if stdout else ""
            stderr_str = stderr.decode("utf-8").strip() if stderr else ""

            if process.returncode != 0:
                error_msg = stderr_str or stdout_str or f"Command failed with code {process.returncode}"
                return CommandResult(
                    success=False,
                    data=None,
                    error=error_msg,
                    raw_output=stdout_str
                )

            # Parse JSON output
            data = None
            if stdout_str:
                try:
                    data = json.loads(stdout_str)
                except json.JSONDecodeError:
                    data = stdout_str

            return CommandResult(
                success=True,
                data=data,
                raw_output=stdout_str
            )

        except asyncio.TimeoutError:
            return CommandResult(
                success=False,
                data=None,
                error=f"Command timed out after {effective_timeout}s"
            )
        except Exception as e:
            return CommandResult(
                success=False,
                data=None,
                error=str(e)
            )

    # =========================================================================
    # Navigation Commands
    # =========================================================================

    async def open(self, url: str) -> CommandResult:
        """
        Navigate to a URL.

        Args:
            url: The URL to navigate to

        Returns:
            CommandResult with navigation status
        """
        return await self._run_command("open", url)

    async def back(self) -> CommandResult:
        """Navigate back in browser history."""
        return await self._run_command("back")

    async def forward(self) -> CommandResult:
        """Navigate forward in browser history."""
        return await self._run_command("forward")

    async def reload(self) -> CommandResult:
        """Reload the current page."""
        return await self._run_command("reload")

    async def url(self) -> CommandResult:
        """Get the current page URL."""
        return await self._run_command("url")

    async def title(self) -> CommandResult:
        """Get the current page title."""
        return await self._run_command("title")

    # =========================================================================
    # Element Interaction Commands
    # =========================================================================

    async def click(self, ref: str) -> CommandResult:
        """
        Click an element.

        Args:
            ref: Element reference (@e1) from snapshot or CSS selector

        Returns:
            CommandResult with click status
        """
        return await self._run_command("click", ref)

    async def dblclick(self, ref: str) -> CommandResult:
        """
        Double-click an element.

        Args:
            ref: Element reference or CSS selector
        """
        return await self._run_command("dblclick", ref)

    async def type(self, ref: str, text: str) -> CommandResult:
        """
        Type text into an element (appends to existing content).

        Args:
            ref: Element reference or CSS selector
            text: Text to type
        """
        return await self._run_command("type", ref, text)

    async def fill(self, ref: str, text: str) -> CommandResult:
        """
        Fill an input field (clears existing content first).

        Args:
            ref: Element reference or CSS selector
            text: Text to fill
        """
        return await self._run_command("fill", ref, text)

    async def clear(self, ref: str) -> CommandResult:
        """
        Clear an input field.

        Args:
            ref: Element reference or CSS selector
        """
        return await self._run_command("clear", ref)

    async def press(self, key: str) -> CommandResult:
        """
        Press a keyboard key.

        Args:
            key: Key name (Enter, Tab, Escape, PageDown, ArrowDown, etc.)
        """
        return await self._run_command("press", key)

    async def hover(self, ref: str) -> CommandResult:
        """
        Hover over an element.

        Args:
            ref: Element reference or CSS selector
        """
        return await self._run_command("hover", ref)

    async def focus(self, ref: str) -> CommandResult:
        """
        Focus an element.

        Args:
            ref: Element reference or CSS selector
        """
        return await self._run_command("focus", ref)

    async def select(self, ref: str, value: str) -> CommandResult:
        """
        Select an option from a dropdown.

        Args:
            ref: Select element reference or CSS selector
            value: Option value to select
        """
        return await self._run_command("select", ref, value)

    async def check(self, ref: str) -> CommandResult:
        """
        Check a checkbox.

        Args:
            ref: Checkbox element reference or CSS selector
        """
        return await self._run_command("check", ref)

    async def uncheck(self, ref: str) -> CommandResult:
        """
        Uncheck a checkbox.

        Args:
            ref: Checkbox element reference or CSS selector
        """
        return await self._run_command("uncheck", ref)

    # =========================================================================
    # Scrolling Commands
    # =========================================================================

    async def scroll(self, direction: str = "down", amount: int = 500) -> CommandResult:
        """
        Scroll the page.

        Args:
            direction: Scroll direction ("up" or "down")
            amount: Pixels to scroll
        """
        return await self._run_command("scroll", direction, str(amount))

    async def scroll_to(self, ref: str) -> CommandResult:
        """
        Scroll an element into view.

        Args:
            ref: Element reference or CSS selector
        """
        return await self._run_command("scroll", ref)

    # =========================================================================
    # State & Content Commands
    # =========================================================================

    async def snapshot(
        self,
        interactive: bool = True,
        compact: bool = True
    ) -> CommandResult:
        """
        Get accessibility tree snapshot with element refs.

        This is the primary way to "see" the page for LLM agents.
        Returns interactive elements with refs like @e1, @e2 that can
        be used for clicking, typing, etc.

        Args:
            interactive: Only return interactive elements (clickable, inputs)
            compact: Use compact output format

        Returns:
            CommandResult with accessibility tree data
        """
        args = ["snapshot"]
        if interactive:
            args.append("-i")
        if compact:
            args.append("-c")
        return await self._run_command(*args)

    async def screenshot(self, path: Optional[str] = None, full_page: bool = False) -> CommandResult:
        """
        Take a screenshot.

        Args:
            path: File path to save screenshot (optional)
            full_page: Capture full scrollable page

        Returns:
            CommandResult with screenshot data or file path
        """
        args = ["screenshot"]
        if path:
            args.extend(["--path", path])
        if full_page:
            args.append("--full-page")
        return await self._run_command(*args)

    async def get_text(self, ref: Optional[str] = None) -> CommandResult:
        """
        Get text content from page or element.

        Args:
            ref: Optional element reference (gets full page if not specified)
        """
        args = ["get", "text"]
        if ref:
            args.append(ref)
        return await self._run_command(*args)

    async def get_html(self, ref: Optional[str] = None) -> CommandResult:
        """
        Get HTML content from page or element.

        Args:
            ref: Optional element reference
        """
        args = ["get", "html"]
        if ref:
            args.append(ref)
        return await self._run_command(*args)

    async def get_attribute(self, ref: str, attr: str) -> CommandResult:
        """
        Get an attribute value from an element.

        Args:
            ref: Element reference or CSS selector
            attr: Attribute name
        """
        return await self._run_command("get", "attribute", ref, attr)

    async def get_value(self, ref: str) -> CommandResult:
        """
        Get the value of an input element.

        Args:
            ref: Input element reference or CSS selector
        """
        return await self._run_command("get", "value", ref)

    # =========================================================================
    # JavaScript Execution
    # =========================================================================

    async def evaluate(self, script: str) -> CommandResult:
        """
        Execute JavaScript code and return the result.

        Args:
            script: JavaScript code to execute

        Returns:
            CommandResult with script return value
        """
        return await self._run_command("evaluate", script)

    # =========================================================================
    # Wait Commands
    # =========================================================================

    async def wait(self, target: str) -> CommandResult:
        """
        Wait for an element or duration.

        Args:
            target: CSS selector to wait for, or milliseconds (e.g., "2000")
        """
        return await self._run_command("wait", target)

    async def wait_for_navigation(self) -> CommandResult:
        """Wait for navigation to complete."""
        return await self._run_command("wait", "navigation")

    async def wait_for_load(self) -> CommandResult:
        """Wait for page load to complete."""
        return await self._run_command("wait", "load")

    # =========================================================================
    # Cookie & Storage Commands
    # =========================================================================

    async def cookies_get(self) -> CommandResult:
        """Get all cookies for the current page."""
        return await self._run_command("cookies", "get")

    async def cookies_set(self, cookies: list[dict]) -> CommandResult:
        """
        Set cookies.

        Args:
            cookies: List of cookie objects with name, value, domain, etc.
        """
        return await self._run_command("cookies", "set", json.dumps(cookies))

    async def cookies_clear(self) -> CommandResult:
        """Clear all cookies."""
        return await self._run_command("cookies", "clear")

    async def storage_get(self, key: Optional[str] = None) -> CommandResult:
        """
        Get localStorage data.

        Args:
            key: Specific key to get (gets all if not specified)
        """
        args = ["storage", "get"]
        if key:
            args.append(key)
        return await self._run_command(*args)

    async def storage_set(self, key: str, value: str) -> CommandResult:
        """
        Set localStorage data.

        Args:
            key: Storage key
            value: Value to store
        """
        return await self._run_command("storage", "set", key, value)

    async def storage_clear(self) -> CommandResult:
        """Clear localStorage."""
        return await self._run_command("storage", "clear")

    # =========================================================================
    # Session Management
    # =========================================================================

    async def close(self) -> CommandResult:
        """Close the browser and end the session."""
        return await self._run_command("close")

    # =========================================================================
    # Tab Management
    # =========================================================================

    async def tab_new(self, url: Optional[str] = None) -> CommandResult:
        """
        Open a new tab.

        Args:
            url: Optional URL to open in new tab
        """
        args = ["tab", "new"]
        if url:
            args.append(url)
        return await self._run_command(*args)

    async def tab_list(self) -> CommandResult:
        """List all open tabs."""
        return await self._run_command("tab", "list")

    async def tab_switch(self, index: int) -> CommandResult:
        """
        Switch to a tab by index.

        Args:
            index: Tab index (0-based)
        """
        return await self._run_command("tab", "switch", str(index))

    async def tab_close(self, index: Optional[int] = None) -> CommandResult:
        """
        Close a tab.

        Args:
            index: Tab index to close (closes current if not specified)
        """
        args = ["tab", "close"]
        if index is not None:
            args.append(str(index))
        return await self._run_command(*args)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_tool_definitions(self) -> list[dict]:
        """
        Get tool definitions for LLM function calling.

        Returns a list of tool definitions compatible with OpenAI/Anthropic/Gemini
        function calling formats.
        """
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
                "description": "Get accessibility tree with element refs (@e1, @e2, etc.). This is how you 'see' the page. Use -i flag for interactive elements only (clickable, inputs).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "interactive": {
                            "type": "boolean",
                            "description": "Only return interactive elements",
                            "default": True
                        }
                    }
                }
            },
            {
                "name": "browser_click",
                "description": "Click an element by its ref (e.g., @e1 from snapshot) or CSS selector",
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
                "description": "Type text into an element (appends to existing content)",
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
                "name": "browser_fill",
                "description": "Fill an input field (clears existing content first)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ref": {"type": "string", "description": "Element ref or selector"},
                        "text": {"type": "string", "description": "Text to fill"}
                    },
                    "required": ["ref", "text"]
                }
            },
            {
                "name": "browser_scroll",
                "description": "Scroll the page up or down",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "direction": {
                            "type": "string",
                            "enum": ["up", "down"],
                            "default": "down"
                        },
                        "amount": {
                            "type": "integer",
                            "description": "Pixels to scroll",
                            "default": 500
                        }
                    }
                }
            },
            {
                "name": "browser_press",
                "description": "Press a keyboard key (Enter, Tab, Escape, PageDown, ArrowDown, etc.)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Key name to press"}
                    },
                    "required": ["key"]
                }
            },
            {
                "name": "browser_wait",
                "description": "Wait for an element (CSS selector) or duration in milliseconds (e.g., '2000' for 2 seconds)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string", "description": "CSS selector or milliseconds"}
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
                "description": "Get text content from the page or a specific element",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ref": {"type": "string", "description": "Optional element ref to get text from"}
                    }
                }
            },
            {
                "name": "browser_screenshot",
                "description": "Take a screenshot of the current page",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to save screenshot"},
                        "full_page": {"type": "boolean", "description": "Capture full scrollable page"}
                    }
                }
            },
            {
                "name": "browser_hover",
                "description": "Hover over an element",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ref": {"type": "string", "description": "Element ref or selector"}
                    },
                    "required": ["ref"]
                }
            }
        ]


# Synchronous wrapper for non-async contexts
class AgentBrowserClientSync:
    """Synchronous wrapper for AgentBrowserClient."""

    def __init__(self, **kwargs):
        self._async_client = AgentBrowserClient(**kwargs)
        self._loop = None

    def _get_loop(self):
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
        return self._loop

    def _run(self, coro):
        return self._get_loop().run_until_complete(coro)

    def open(self, url: str) -> CommandResult:
        return self._run(self._async_client.open(url))

    def click(self, ref: str) -> CommandResult:
        return self._run(self._async_client.click(ref))

    def type(self, ref: str, text: str) -> CommandResult:
        return self._run(self._async_client.type(ref, text))

    def fill(self, ref: str, text: str) -> CommandResult:
        return self._run(self._async_client.fill(ref, text))

    def snapshot(self, interactive: bool = True, compact: bool = True) -> CommandResult:
        return self._run(self._async_client.snapshot(interactive, compact))

    def evaluate(self, script: str) -> CommandResult:
        return self._run(self._async_client.evaluate(script))

    def wait(self, target: str) -> CommandResult:
        return self._run(self._async_client.wait(target))

    def press(self, key: str) -> CommandResult:
        return self._run(self._async_client.press(key))

    def scroll(self, direction: str = "down", amount: int = 500) -> CommandResult:
        return self._run(self._async_client.scroll(direction, amount))

    def close(self) -> CommandResult:
        return self._run(self._async_client.close())

    def __enter__(self):
        self._run(self._async_client._ensure_installed())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.close()
        except Exception:
            pass


if __name__ == "__main__":
    # Quick test
    async def test():
        async with AgentBrowserClient(session="test", headed=True) as browser:
            result = await browser.open("https://example.com")
            print(f"Open: {result}")

            result = await browser.snapshot()
            print(f"Snapshot: {result.data}")

            await asyncio.sleep(2)

    asyncio.run(test())
