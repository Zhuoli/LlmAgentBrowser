"""
Twitter/X Tweet Fetcher using Chrome DevTools MCP + LLM

This implementation uses Chrome DevTools MCP server for browser control,
combined with LLM function calling for intelligent orchestration.

Architecture:
1. MCP Client connects to chrome-devtools-mcp server (via npx)
2. LLM receives available tools and decides actions
3. Tool calls are executed via MCP protocol
4. Results flow back to LLM for next decision

Supported LLM Models:
- Google Gemini 3 Pro
- Claude Opus 4.5
- OpenAI GPT-5.2

Usage:
    uv run python twitter_fetcher_mcp.py --model gemini
    uv run python twitter_fetcher_mcp.py --model claude
    uv run python twitter_fetcher_mcp.py --all
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, cast

from dotenv import load_dotenv

load_dotenv()

# MCP imports
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.types import Tool

# Import google.genai at module level for Gemini support (new SDK with MCP support)
try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None  # type: ignore
    genai_types = None  # type: ignore

# Logging setup
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Setup logging with both file and console handlers."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"mcp_browser_{timestamp}.log"

    logger = logging.getLogger("mcp_browser")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.handlers.clear()

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(f"{Colors.BLUE}[MCP]{Colors.ENDC} %(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    logger.info(f"Logging initialized. Log file: {log_file}")
    return logger


logger: Optional[logging.Logger] = None


@dataclass
class Tweet:
    """Represents a single tweet"""
    author: str
    handle: str
    content: str
    link: str
    likes: Optional[int] = None
    retweets: Optional[int] = None
    replies: Optional[int] = None
    timestamp: Optional[str] = None


@dataclass
class ModelResult:
    """Stores the result of running a model"""
    model_name: str
    model_type: str
    tweets: list[Tweet] = field(default_factory=list)
    raw_output: str = ""
    execution_time: float = 0.0
    success: bool = False
    error_message: Optional[str] = None
    tool_calls_count: int = 0


def print_header(text: str) -> None:
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.ENDC}\n")


def print_info(message: str) -> None:
    print(f"{Colors.YELLOW}[INFO]{Colors.ENDC} {message}")


def print_error(message: str) -> None:
    print(f"{Colors.RED}[ERROR]{Colors.ENDC} {message}")


def print_success(message: str) -> None:
    print(f"{Colors.GREEN}[SUCCESS]{Colors.ENDC} {message}")


def print_tool_call(tool_name: str, args: Any) -> None:
    args_str = json.dumps(args, indent=None) if isinstance(args, dict) else str(args)
    print(f"{Colors.CYAN}[TOOL]{Colors.ENDC} {tool_name}({args_str[:80]}...)")


def clean_schema_for_gemini(schema: dict) -> dict:
    """Clean JSON Schema to remove fields not supported by Gemini.

    Gemini's FunctionDeclaration only supports a subset of JSON Schema.
    """
    # Fields not supported by Gemini
    unsupported_fields = {
        "$schema", "exclusiveMinimum", "exclusiveMaximum",
        "additionalProperties", "patternProperties", "allOf", "anyOf", "oneOf",
        "not", "if", "then", "else", "$ref", "$defs", "definitions",
        "contentMediaType", "contentEncoding", "examples", "default",
        "deprecated", "readOnly", "writeOnly", "$id", "$anchor", "$comment",
    }

    def clean_recursive(obj: Any) -> Any:
        if isinstance(obj, dict):
            cleaned = {}
            for key, value in obj.items():
                if key not in unsupported_fields:
                    cleaned[key] = clean_recursive(value)
            return cleaned
        elif isinstance(obj, list):
            return [clean_recursive(item) for item in obj]
        else:
            return obj

    return clean_recursive(schema)


def mcp_tools_to_openai_format(tools: list[Tool]) -> list[dict]:
    """Convert MCP tools to OpenAI function calling format."""
    openai_tools = []
    for tool in tools:
        openai_tool = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema if tool.inputSchema else {"type": "object", "properties": {}},
            }
        }
        openai_tools.append(openai_tool)
    return openai_tools


def mcp_tools_to_anthropic_format(tools: list[Tool]) -> list[dict]:
    """Convert MCP tools to Anthropic tool format."""
    anthropic_tools = []
    for tool in tools:
        anthropic_tool = {
            "name": tool.name,
            "description": tool.description or "",
            "input_schema": tool.inputSchema if tool.inputSchema else {"type": "object", "properties": {}},
        }
        anthropic_tools.append(anthropic_tool)
    return anthropic_tools


def get_tweet_extraction_js(num_tweets: int = 5) -> str:
    """JavaScript code to extract tweets from Twitter DOM."""
    return f"""
(function() {{
    const tweets = [];
    const articles = document.querySelectorAll('article[data-testid="tweet"]');
    for (let i = 0; i < Math.min(articles.length, {num_tweets}); i++) {{
        const article = articles[i];
        try {{
            const authorEl = article.querySelector('div[data-testid="User-Name"]');
            const author = authorEl?.querySelector('span')?.textContent || '';
            const handleEl = authorEl?.querySelectorAll('span');
            let handle = '';
            for (const span of handleEl || []) {{
                if (span.textContent?.startsWith('@')) {{
                    handle = span.textContent;
                    break;
                }}
            }}
            const contentEl = article.querySelector('div[data-testid="tweetText"]');
            const content = contentEl?.textContent || '';
            const linkEl = article.querySelector('a[href*="/status/"]');
            const link = linkEl ? 'https://x.com' + linkEl.getAttribute('href') : '';
            const timeEl = article.querySelector('time');
            const timestamp = timeEl?.getAttribute('datetime') || timeEl?.textContent || '';
            if (content || author) {{
                tweets.push({{ author, handle, content, link, timestamp }});
            }}
        }} catch (e) {{ }}
    }}
    return JSON.stringify(tweets, null, 2);
}})()
"""


# macOS Chrome paths (same as browser-use version)
CHROME_USER_DATA_DIR = os.path.expanduser("~/Library/Application Support/Google/Chrome")
CHROME_PROFILE = "Default"


class MCPBrowserClient:
    """Client that connects to Chrome DevTools MCP server."""

    def __init__(self, use_profile: bool = True):
        self.session: Optional[ClientSession] = None
        self.tools: list[Tool] = []
        self._read = None
        self._write = None
        self.use_profile = use_profile

    async def connect(self):
        """Connect to Chrome DevTools MCP server via npx with Chrome profile."""
        # Build args for chrome-devtools-mcp
        # Use --userDataDir and --profile to use the user's Chrome profile
        # This requires Chrome to NOT be running (close all Chrome windows first)
        mcp_args = ["-y", "chrome-devtools-mcp@latest"]

        if self.use_profile:
            # Use user's Chrome profile (where they're logged into Twitter)
            # The user must close Chrome before running this
            mcp_args.extend([
                "--userDataDir", CHROME_USER_DATA_DIR,
                "--profile", CHROME_PROFILE,
            ])
        else:
            # Use isolated profile (temp profile, auto-cleaned up)
            # Works even with Chrome already running
            mcp_args.append("--isolated")

        server_params = StdioServerParameters(
            command="npx",
            args=mcp_args,
            env={
                **os.environ,
                "PATH": os.environ.get("PATH", ""),
            }
        )

        if logger:
            if self.use_profile:
                logger.info(f"Starting Chrome DevTools MCP with profile: {CHROME_PROFILE}")
                logger.info(f"User data dir: {CHROME_USER_DATA_DIR}")
            else:
                logger.info("Starting Chrome DevTools MCP (isolated profile)")

        # Create the stdio client context
        self._stdio_context = stdio_client(server_params)
        self._read, self._write = await self._stdio_context.__aenter__()

        # Create session
        self.session = ClientSession(self._read, self._write)
        await self.session.__aenter__()
        await self.session.initialize()

        # Get available tools
        tools_result = await self.session.list_tools()
        self.tools = tools_result.tools

        if logger:
            logger.info(f"Connected! Available tools: {[t.name for t in self.tools]}")

        return self

    async def disconnect(self):
        """Disconnect from MCP server."""
        if self.session:
            await self.session.__aexit__(None, None, None)
        if hasattr(self, '_stdio_context'):
            await self._stdio_context.__aexit__(None, None, None)

    async def call_tool(self, name: str, arguments: dict) -> Any:
        """Call an MCP tool and return the result."""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")

        if logger:
            logger.debug(f"Calling tool: {name} with args: {arguments}")

        result = await self.session.call_tool(name, arguments)

        if logger:
            logger.debug(f"Tool result: {result}")

        return result


class LLMOrchestrator:
    """Orchestrates LLM with MCP tools for browser automation."""

    def __init__(self, model_type: str, mcp_client: MCPBrowserClient):
        self.model_type = model_type
        self.mcp_client = mcp_client
        self.tool_calls_count = 0

    async def run_task(self, task: str, max_steps: int = 20) -> str:
        """Run a task using LLM to orchestrate MCP tools."""
        if self.model_type == "gemini":
            return await self._run_with_gemini(task, max_steps)
        elif self.model_type == "claude":
            return await self._run_with_claude(task, max_steps)
        elif self.model_type == "openai":
            return await self._run_with_openai(task, max_steps)
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

    async def _run_with_gemini(self, task: str, max_steps: int) -> str:
        """Run task using Google Gemini with MCP tools via manual function calling loop.

        We use manual function calling to have full control over the multi-step process.
        """
        if not GEMINI_AVAILABLE or genai is None or genai_types is None:
            raise ValueError("google-genai package is not installed")

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")

        # Create Gemini client
        client = genai.Client(api_key=api_key)

        if self.mcp_client.session is None:
            raise RuntimeError("MCP session not connected")

        if logger:
            logger.info("Using Gemini with MCP tools (manual function calling loop)")

        # Convert MCP tools to Gemini function declarations
        tool_declarations = []
        for tool in self.mcp_client.tools:
            # Clean the schema - remove unsupported JSON Schema fields
            params = None
            if tool.inputSchema:
                params = clean_schema_for_gemini(tool.inputSchema)

            tool_declarations.append(genai_types.FunctionDeclaration(
                name=tool.name,
                description=tool.description or "",
                parameters=params,
            ))

        # Create chat with tools
        chat = client.aio.chats.create(
            model="gemini-2.0-flash",
            config=genai_types.GenerateContentConfig(
                tools=[genai_types.Tool(function_declarations=tool_declarations)],
                automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=True),
                temperature=0.0,
            ),
        )

        # Send initial task
        response = await chat.send_message(task)
        final_result = ""

        for step in range(max_steps):
            if logger:
                logger.info(f"Step {step + 1}/{max_steps}")

            # Check for function calls in response
            function_calls = []
            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        function_calls.append(part.function_call)

            if not function_calls:
                # No more function calls - get final text
                final_result = response.text if response.text else ""
                break

            # Execute function calls via MCP
            function_responses = []
            for fc in function_calls:
                tool_name = fc.name
                tool_args = dict(fc.args) if fc.args else {}

                print_tool_call(tool_name, tool_args)
                self.tool_calls_count += 1

                try:
                    result = await self.mcp_client.call_tool(tool_name, tool_args)
                    result_text = str(result.content[0].text if result.content else result)
                except Exception as e:
                    result_text = f"Error: {str(e)}"

                if logger:
                    logger.info(f"Tool {tool_name} result: {result_text[:200]}...")

                function_responses.append(genai_types.Part.from_function_response(
                    name=tool_name,
                    response={"result": result_text[:8000]}  # Truncate large responses
                ))

            # Send function responses back
            response = await chat.send_message(function_responses)

        return final_result

    async def _run_with_claude(self, task: str, max_steps: int) -> str:
        """Run task using Claude with tool use."""
        import anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        client = anthropic.Anthropic(api_key=api_key)
        tools = mcp_tools_to_anthropic_format(self.mcp_client.tools)

        messages: list[Any] = [{"role": "user", "content": task}]
        final_result = ""

        for step in range(max_steps):
            if logger:
                logger.info(f"Step {step + 1}/{max_steps}")

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                tools=tools,  # type: ignore[arg-type]
                messages=messages,  # type: ignore[arg-type]
            )

            # Process response
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            # Check for tool use
            tool_use_blocks = [b for b in assistant_content if b.type == "tool_use"]

            if not tool_use_blocks:
                # No tool use, extract text result
                text_blocks = [b for b in assistant_content if b.type == "text"]
                if text_blocks:
                    final_result = text_blocks[0].text
                break

            # Execute tool calls
            tool_results: list[dict[str, Any]] = []
            for tool_use in tool_use_blocks:
                tool_name = tool_use.name
                tool_args = cast(dict[str, Any], tool_use.input)

                print_tool_call(tool_name, tool_args)
                self.tool_calls_count += 1

                try:
                    result = await self.mcp_client.call_tool(tool_name, tool_args)
                    result_text = str(result.content[0].text if result.content else result)
                except Exception as e:
                    result_text = f"Error: {str(e)}"

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result_text[:10000]  # Truncate large responses
                })

            messages.append({"role": "user", "content": tool_results})

            if response.stop_reason == "end_turn":
                break

        return final_result

    async def _run_with_openai(self, task: str, max_steps: int) -> str:
        """Run task using OpenAI with function calling."""
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        client = OpenAI(api_key=api_key)
        tools = mcp_tools_to_openai_format(self.mcp_client.tools)

        messages: list[Any] = [{"role": "user", "content": task}]
        final_result = ""

        for step in range(max_steps):
            if logger:
                logger.info(f"Step {step + 1}/{max_steps}")

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,  # type: ignore[arg-type]
                tools=tools,  # type: ignore[arg-type]
                tool_choice="auto",
                temperature=0.0,
            )

            message = response.choices[0].message
            messages.append(message.model_dump())

            if not message.tool_calls:
                # No tool calls, we're done
                final_result = message.content or ""
                break

            # Execute tool calls
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                print_tool_call(tool_name, tool_args)
                self.tool_calls_count += 1

                try:
                    result = await self.mcp_client.call_tool(tool_name, tool_args)
                    result_text = str(result.content[0].text if result.content else result)
                except Exception as e:
                    result_text = f"Error: {str(e)}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_text[:10000]
                })

        return final_result


def parse_tweets_from_json(raw_output: str) -> list[Tweet]:
    """Parse tweets from JSON output."""
    import re

    tweets = []

    # Extract JSON from markdown code blocks if present
    code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw_output)
    if code_block_match:
        raw_output = code_block_match.group(1).strip()

    # Try to find JSON array
    json_match = re.search(r'\[[\s\S]*\]', raw_output)
    if json_match:
        try:
            data = json.loads(json_match.group())
            for item in data:
                tweet = Tweet(
                    author=item.get("author", "Unknown"),
                    handle=item.get("handle", ""),
                    content=item.get("content", item.get("text", "")),
                    link=item.get("link", item.get("url", "")),
                    likes=item.get("likes"),
                    retweets=item.get("retweets"),
                    replies=item.get("replies"),
                    timestamp=item.get("timestamp"),
                )
                tweets.append(tweet)
        except json.JSONDecodeError:
            pass

    return tweets


def save_tweets_to_markdown(result: ModelResult, output_dir: Path) -> Path:
    """Save the tweets to a structured Markdown file."""
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_model_name = result.model_type.replace(" ", "_").replace("-", "_")
    filename = f"tweets_mcp_{safe_model_name}_{timestamp}.md"
    filepath = output_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Twitter/X Timeline Tweets (MCP)\n\n")
        f.write(f"**Model:** {result.model_name}\n\n")
        f.write(f"**Method:** Chrome DevTools MCP\n\n")
        f.write(f"**Fetched at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Execution time:** {result.execution_time:.2f} seconds\n\n")
        f.write(f"**Tool calls:** {result.tool_calls_count}\n\n")
        f.write("---\n\n")

        if result.tweets:
            for i, tweet in enumerate(result.tweets, 1):
                f.write(f"## Tweet {i}\n\n")
                f.write(f"| Field | Value |\n")
                f.write(f"|-------|-------|\n")
                f.write(f"| **Author** | {tweet.author} |\n")
                if tweet.handle:
                    f.write(f"| **Handle** | {tweet.handle} |\n")
                if tweet.link:
                    f.write(f"| **Link** | [{tweet.link}]({tweet.link}) |\n")
                if tweet.timestamp:
                    f.write(f"| **Time** | {tweet.timestamp} |\n")
                f.write("\n")
                f.write(f"### Content\n\n")
                f.write(f"> {tweet.content}\n\n")
                f.write("---\n\n")
        else:
            f.write("*No tweets were extracted.*\n\n")
            if result.raw_output:
                f.write("## Raw Output\n\n")
                f.write("```\n")
                f.write(result.raw_output[:2000])
                f.write("\n```\n")

        if result.error_message:
            f.write(f"\n## Error\n\n")
            f.write(f"```\n{result.error_message}\n```\n")

    return filepath


async def fetch_tweets_with_mcp(model_type: str, num_tweets: int = 5, num_scrolls: int = 3, isolated: bool = False) -> ModelResult:
    """Fetch tweets using Chrome DevTools MCP + LLM."""
    start_time = time.time()
    result = ModelResult(model_name="", model_type=model_type)

    model_names = {
        "gemini": "Google Gemini 2.0 Flash",
        "claude": "Claude Sonnet 4",
        "openai": "OpenAI GPT-4o",
    }
    result.model_name = model_names.get(model_type, model_type)

    print(f"{Colors.CYAN}[Model]{Colors.ENDC} {Colors.BOLD}{result.model_name}{Colors.ENDC}")
    if isolated:
        print_info("Using isolated Chrome profile (temporary, no login)")
    else:
        print_info(f"Chrome profile: {CHROME_PROFILE}")
        print_info(f"User data dir: {CHROME_USER_DATA_DIR}")
        print_info("Please close all Chrome windows before running...")
    print_info("Connecting to Chrome DevTools MCP server...")

    mcp_client = MCPBrowserClient(use_profile=not isolated)

    try:
        await mcp_client.connect()
        print_success(f"Connected! {len(mcp_client.tools)} tools available")

        # Create orchestrator
        orchestrator = LLMOrchestrator(model_type, mcp_client)

        # Define the task with explicit JavaScript extraction
        js_code = get_tweet_extraction_js(num_tweets)

        task = f"""You are a browser automation agent. Complete this task step by step:

1. First, create a new browser page using new_page tool
2. Navigate to https://x.com using navigate_page tool
3. Wait for the page to load (use wait_for tool with selector "article" and timeout 10000)
4. Scroll down {num_scrolls} times to load more tweets:
   - Use evaluate_script with expression "window.scrollBy(0, 800)" for each scroll
   - After each scroll, wait briefly using evaluate_script with "await new Promise(r => setTimeout(r, 2000))"
5. After scrolling, extract tweets using evaluate_script with this JavaScript:
{js_code}

6. Return the extracted JSON data as your final response.

IMPORTANT:
- Do NOT use take_screenshot unless specifically needed
- Focus on completing the task efficiently
- Return the JSON array of tweets as your final answer
"""

        print_info("Starting LLM orchestration...")
        raw_output = await orchestrator.run_task(task, max_steps=25)

        result.raw_output = raw_output
        result.tool_calls_count = orchestrator.tool_calls_count

        if raw_output:
            result.tweets = parse_tweets_from_json(raw_output)
            result.success = len(result.tweets) > 0
            if result.success:
                print_success(f"Extracted {len(result.tweets)} tweets in {orchestrator.tool_calls_count} tool calls")
            else:
                result.error_message = "Could not parse tweets from output"
                print_error(result.error_message)
        else:
            result.error_message = "No output from agent"
            print_error(result.error_message)

    except Exception as e:
        result.error_message = str(e)
        print_error(f"Failed: {e}")
        if logger:
            logger.exception("Error during execution")
    finally:
        await mcp_client.disconnect()

    result.execution_time = time.time() - start_time
    return result


def print_result_summary(result: ModelResult) -> None:
    """Print a summary of the result."""
    print(f"\n{Colors.CYAN}Execution Time:{Colors.ENDC} {result.execution_time:.2f}s")
    print(f"{Colors.CYAN}Tool Calls:{Colors.ENDC} {result.tool_calls_count}")
    print(f"{Colors.CYAN}Status:{Colors.ENDC} {'Success' if result.success else 'Failed'}")
    print(f"{Colors.CYAN}Tweets Found:{Colors.ENDC} {len(result.tweets)}")

    if result.tweets:
        print(f"\n{Colors.BOLD}Preview:{Colors.ENDC}")
        for i, tweet in enumerate(result.tweets[:3], 1):
            content_preview = tweet.content[:80] + "..." if len(tweet.content) > 80 else tweet.content
            print(f"  {i}. {tweet.handle}: {content_preview}")
        if len(result.tweets) > 3:
            print(f"  ... and {len(result.tweets) - 3} more")


def print_comparison(results: list[ModelResult]) -> None:
    """Print a comparison table of all results."""
    print_header("Model Comparison (MCP)")

    print(f"{'Model':<25} {'Status':<10} {'Time':<10} {'Tools':<8} {'Tweets':<8}")
    print("-" * 65)

    for r in results:
        status = "OK" if r.success else "FAIL"
        print(f"{r.model_name:<25} {status:<10} {r.execution_time:<10.2f} {r.tool_calls_count:<8} {len(r.tweets):<8}")

    successful = [r for r in results if r.success]
    if successful:
        fastest = min(successful, key=lambda x: x.execution_time)
        fewest_calls = min(successful, key=lambda x: x.tool_calls_count)
        print(f"\n{Colors.GREEN}Fastest:{Colors.ENDC} {fastest.model_name} ({fastest.execution_time:.2f}s)")
        print(f"{Colors.GREEN}Most efficient:{Colors.ENDC} {fewest_calls.model_name} ({fewest_calls.tool_calls_count} tool calls)")


async def main():
    parser = argparse.ArgumentParser(
        description="Fetch tweets using Chrome DevTools MCP + LLM"
    )
    parser.add_argument(
        "--model",
        choices=["gemini", "claude", "openai"],
        help="LLM model to use"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all models for comparison"
    )
    parser.add_argument(
        "--tweets",
        type=int,
        default=5,
        help="Number of tweets to fetch (default: 5)"
    )
    parser.add_argument(
        "--scrolls",
        type=int,
        default=3,
        help="Number of scrolls (default: 3)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output",
        help="Output directory (default: output)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    parser.add_argument(
        "--isolated",
        action="store_true",
        help="Use isolated Chrome profile (no login, but works with Chrome running)"
    )

    args = parser.parse_args()

    if not args.model and not args.all:
        parser.print_help()
        print(f"\n{Colors.YELLOW}Please specify --model <name> or --all{Colors.ENDC}")
        sys.exit(1)

    output_dir = Path(args.output)

    global logger
    logger = setup_logging(args.log_level)

    print_header("Twitter/X Fetcher (Chrome DevTools MCP)")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Tweets to fetch: {args.tweets}")
    print(f"Scroll count: {args.scrolls}")
    print(f"Output directory: {output_dir.absolute()}")

    results = []
    saved_files = []

    if args.all:
        models = ["gemini", "claude", "openai"]
        for model in models:
            print_header(f"Testing: {model.upper()}")
            try:
                result = await fetch_tweets_with_mcp(model, args.tweets, args.scrolls, args.isolated)
                results.append(result)
                print_result_summary(result)

                filepath = save_tweets_to_markdown(result, output_dir)
                saved_files.append(filepath)
                print_success(f"Saved to: {filepath}")

            except ValueError as e:
                print_error(f"Skipping {model}: {e}")
                results.append(ModelResult(
                    model_name=model,
                    model_type=model,
                    error_message=str(e)
                ))

        print_comparison(results)
    else:
        result = await fetch_tweets_with_mcp(args.model, args.tweets, args.scrolls, args.isolated)
        results.append(result)
        print_result_summary(result)

        filepath = save_tweets_to_markdown(result, output_dir)
        saved_files.append(filepath)
        print_success(f"Saved to: {filepath}")

    if saved_files:
        print_header("Output Files")
        for f in saved_files:
            print(f"  - {f}")

    return results


if __name__ == "__main__":
    asyncio.run(main())
