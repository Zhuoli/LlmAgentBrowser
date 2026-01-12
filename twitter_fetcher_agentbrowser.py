"""
Twitter/X Tweet Fetcher using agent-browser + LLM

This implementation uses Vercel Labs' agent-browser CLI for browser automation.
agent-browser is optimized for AI agents with ref-based element selection.

Architecture:
1. Python wrapper calls agent-browser CLI commands via subprocess
2. agent-browser uses Playwright to control headless Chromium
3. LLM orchestrates browser actions using tool calling
4. Ref-based selection (@e1, @e2) from accessibility snapshots

Key Features:
- Ref-based element selection (optimal for LLMs)
- Session isolation for parallel automation
- 100+ browser automation commands
- Headless by default (--headed for debugging)

Supported LLM Models:
- Google Gemini 2.0 Flash
- Claude Sonnet 4
- OpenAI GPT-4o

Prerequisites:
- npm install -g agent-browser
- agent-browser install  # Downloads Chromium

Note: Unlike Browser MCP, this uses a fresh browser instance.
Twitter login credentials may be required (via env vars or manual login).

Usage:
    uv run python twitter_fetcher_agentbrowser.py --model gemini
    uv run python twitter_fetcher_agentbrowser.py --model claude --headed
    uv run python twitter_fetcher_agentbrowser.py --all
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, cast

from dotenv import load_dotenv

load_dotenv()

from agent_browser_client import AgentBrowserClient, CommandResult

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
    log_file = LOG_DIR / f"agentbrowser_{timestamp}.log"

    logger = logging.getLogger("agentbrowser")
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
    console_formatter = logging.Formatter(f"{Colors.BLUE}[AgentBrowser]{Colors.ENDC} %(message)s")
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
    print(f"{Colors.CYAN}[TOOL]{Colors.ENDC} {tool_name}({args_str[:80]}{'...' if len(args_str) > 80 else ''})")


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


def clean_schema_for_gemini(schema: dict) -> dict:
    """Clean JSON Schema to remove fields not supported by Gemini."""
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


def tools_to_anthropic_format(tools: list[dict]) -> list[dict]:
    """Convert tools to Anthropic tool format."""
    anthropic_tools = []
    for tool in tools:
        anthropic_tool = {
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": {
                "type": "object",
                "properties": tool["parameters"].get("properties", {}),
                "required": tool["parameters"].get("required", [])
            }
        }
        anthropic_tools.append(anthropic_tool)
    return anthropic_tools


def tools_to_openai_format(tools: list[dict]) -> list[dict]:
    """Convert tools to OpenAI function calling format."""
    openai_tools = []
    for tool in tools:
        openai_tool = {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"]
            }
        }
        openai_tools.append(openai_tool)
    return openai_tools


class AgentBrowserOrchestrator:
    """Orchestrates LLM with agent-browser tools."""

    def __init__(self, model_type: str, browser: AgentBrowserClient):
        self.model_type = model_type
        self.browser = browser
        self.tool_calls_count = 0
        self.tools = browser.get_tool_definitions()

    async def execute_tool(self, name: str, args: dict) -> str:
        """Execute a browser tool and return result as string."""
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
            elif name == "browser_fill":
                result = await self.browser.fill(args["ref"], args["text"])
            elif name == "browser_scroll":
                result = await self.browser.scroll(
                    args.get("direction", "down"),
                    args.get("amount", 500)
                )
            elif name == "browser_press":
                result = await self.browser.press(args["key"])
            elif name == "browser_wait":
                result = await self.browser.wait(args["target"])
            elif name == "browser_evaluate":
                result = await self.browser.evaluate(args["script"])
            elif name == "browser_get_text":
                result = await self.browser.get_text(args.get("ref"))
            elif name == "browser_screenshot":
                result = await self.browser.screenshot(
                    args.get("path"),
                    args.get("full_page", False)
                )
            elif name == "browser_hover":
                result = await self.browser.hover(args["ref"])
            else:
                return f"Unknown tool: {name}"

            if not result.success:
                return f"Error: {result.error}"

            # Format result for LLM
            if result.data is not None:
                if isinstance(result.data, (dict, list)):
                    return json.dumps(result.data, indent=2)[:8000]
                return str(result.data)[:8000]
            return "Success"

        except Exception as e:
            return f"Error: {str(e)}"

    async def run_task(self, task: str, max_steps: int = 25) -> str:
        """Run a task using LLM to orchestrate browser tools."""
        if self.model_type == "gemini":
            return await self._run_with_gemini(task, max_steps)
        elif self.model_type == "claude":
            return await self._run_with_claude(task, max_steps)
        elif self.model_type == "openai":
            return await self._run_with_openai(task, max_steps)
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

    async def _run_with_gemini(self, task: str, max_steps: int) -> str:
        """Run task using Google Gemini with function calling."""
        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError:
            raise ValueError("google-genai package is not installed")

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")

        client = genai.Client(api_key=api_key)

        if logger:
            logger.info("Using Gemini with agent-browser tools")

        # Convert tools to Gemini function declarations
        tool_declarations = []
        for tool in self.tools:
            params = clean_schema_for_gemini(tool["parameters"])
            tool_declarations.append(genai_types.FunctionDeclaration(
                name=tool["name"],
                description=tool["description"],
                parameters=params,
            ))

        chat = client.aio.chats.create(
            model="gemini-2.0-flash",
            config=genai_types.GenerateContentConfig(
                tools=[genai_types.Tool(function_declarations=tool_declarations)],
                automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=True),
                temperature=0.0,
            ),
        )

        response = await chat.send_message(task)
        final_result = ""

        for step in range(max_steps):
            if logger:
                logger.info(f"Step {step + 1}/{max_steps}")

            function_calls = []
            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        function_calls.append(part.function_call)

            if not function_calls:
                final_result = response.text if response.text else ""
                break

            function_responses = []
            for fc in function_calls:
                tool_name = fc.name
                tool_args = dict(fc.args) if fc.args else {}

                print_tool_call(tool_name, tool_args)
                result_text = await self.execute_tool(tool_name, tool_args)

                if logger:
                    logger.info(f"Tool {tool_name} result: {result_text[:200]}...")

                function_responses.append(genai_types.Part.from_function_response(
                    name=tool_name,
                    response={"result": result_text}
                ))

            response = await chat.send_message(function_responses)

        return final_result

    async def _run_with_claude(self, task: str, max_steps: int) -> str:
        """Run task using Claude with tool use."""
        import anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        client = anthropic.Anthropic(api_key=api_key)
        tools = tools_to_anthropic_format(self.tools)

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

            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            tool_use_blocks = [b for b in assistant_content if b.type == "tool_use"]

            if not tool_use_blocks:
                text_blocks = [b for b in assistant_content if b.type == "text"]
                if text_blocks:
                    final_result = text_blocks[0].text
                break

            tool_results: list[dict[str, Any]] = []
            for tool_use in tool_use_blocks:
                tool_name = tool_use.name
                tool_args = cast(dict[str, Any], tool_use.input)

                print_tool_call(tool_name, tool_args)
                result_text = await self.execute_tool(tool_name, tool_args)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result_text[:10000]
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
        tools = tools_to_openai_format(self.tools)

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
                final_result = message.content or ""
                break

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                print_tool_call(tool_name, tool_args)
                result_text = await self.execute_tool(tool_name, tool_args)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_text[:10000]
                })

        return final_result


def parse_tweets_from_json(raw_output: str) -> list[Tweet]:
    """Parse tweets from JSON output."""
    tweets = []

    # Try to extract JSON from markdown code blocks
    code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw_output)
    if code_block_match:
        raw_output = code_block_match.group(1).strip()

    # Find JSON array in output
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
    filename = f"tweets_agentbrowser_{safe_model_name}_{timestamp}.md"
    filepath = output_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Twitter/X Timeline Tweets (agent-browser)\n\n")
        f.write(f"**Model:** {result.model_name}\n\n")
        f.write(f"**Method:** agent-browser (Playwright/Chromium)\n\n")
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


async def fetch_tweets_with_agentbrowser(
    model_type: str,
    num_tweets: int = 5,
    num_scrolls: int = 3,
    headed: bool = False,
    use_chrome_profile: bool = False,
    chrome_profile_path: Optional[str] = None
) -> ModelResult:
    """Fetch tweets using agent-browser + LLM.

    Args:
        model_type: LLM model to use (gemini, claude, openai)
        num_tweets: Number of tweets to fetch
        num_scrolls: Number of page scrolls
        headed: Show browser window
        use_chrome_profile: Use default Chrome profile (with existing logins)
        chrome_profile_path: Custom path to Chrome user data directory
    """
    start_time = time.time()
    result = ModelResult(model_name="", model_type=model_type)

    model_names = {
        "gemini": "Google Gemini 2.0 Flash",
        "claude": "Claude Sonnet 4",
        "openai": "OpenAI GPT-4o",
    }
    result.model_name = model_names.get(model_type, model_type)

    print(f"{Colors.CYAN}[Model]{Colors.ENDC} {Colors.BOLD}{result.model_name}{Colors.ENDC}")

    # Determine Chrome profile settings
    executable_path = None
    user_data_dir = None

    if use_chrome_profile or chrome_profile_path:
        # Use installed Chrome instead of bundled Chromium
        if sys.platform == "darwin":  # macOS
            executable_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            default_profile = os.path.expanduser("~/Library/Application Support/Google/Chrome")
        elif sys.platform == "win32":  # Windows
            executable_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            default_profile = os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data")
        else:  # Linux
            executable_path = "/usr/bin/google-chrome"
            default_profile = os.path.expanduser("~/.config/google-chrome")

        user_data_dir = chrome_profile_path or default_profile
        print_info(f"Using Chrome with profile: {user_data_dir}")
        # Force headed mode when using Chrome profile
        headed = True
    else:
        print_info("Using agent-browser (Playwright/Chromium)")

    if headed:
        print_info("Running in headed mode - browser window visible")
    else:
        print_info("Running headless (use --headed to see browser)")
    print_info("Connecting to agent-browser...")

    session_name = f"twitter_{model_type}_{int(time.time())}"

    try:
        async with AgentBrowserClient(
            session=session_name,
            headed=headed,
            executable_path=executable_path,
            user_data_dir=user_data_dir
        ) as browser:
            print_success("Connected to agent-browser")

            orchestrator = AgentBrowserOrchestrator(model_type, browser)

            js_code = get_tweet_extraction_js(num_tweets)

            task = f"""You are a browser automation agent using agent-browser tools.

WORKFLOW FOR FETCHING TWEETS:

1. Navigate to Twitter/X:
   - Use browser_open with url "https://x.com"

2. Wait for page load:
   - Use browser_wait with target "3000" (3 seconds)

3. Take a snapshot to see the page:
   - Use browser_snapshot with interactive=true
   - This returns refs like @e1, @e2 for interactive elements

4. Check if login is required:
   - If you see a login form, the user needs to login
   - For now, try to proceed - Twitter may show some content without login

5. Scroll to load more tweets:
   - Repeat {num_scrolls} times:
     a. Use browser_press with key "PageDown"
     b. Use browser_wait with target "2000"

6. Extract tweets using JavaScript:
   - Use browser_evaluate with this script:

{js_code}

7. Return the JSON array of tweets from the evaluate result.

IMPORTANT TIPS:
- Use refs from browser_snapshot (e.g., @e1) for clicking/typing
- After any navigation or click, take a new snapshot to see updated page
- The JavaScript extracts: author, handle, content, link, timestamp
- Return ONLY the JSON array of tweets at the end

Begin the task now.
"""

            print_info("Starting LLM orchestration...")
            raw_output = await orchestrator.run_task(task, max_steps=30)

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
    print_header("Model Comparison (agent-browser)")

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
        description="Fetch tweets using agent-browser (Playwright) + LLM"
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
        "--headed",
        action="store_true",
        help="Run browser in headed mode (visible window)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    parser.add_argument(
        "--use-chrome-profile",
        action="store_true",
        help="Use your default Chrome profile (with existing logins like Twitter)"
    )
    parser.add_argument(
        "--chrome-profile-path",
        type=str,
        default=None,
        help="Custom path to Chrome user data directory"
    )

    args = parser.parse_args()

    if not args.model and not args.all:
        parser.print_help()
        print(f"\n{Colors.YELLOW}Please specify --model <name> or --all{Colors.ENDC}")
        sys.exit(1)

    output_dir = Path(args.output)

    global logger
    logger = setup_logging(args.log_level)

    print_header("Twitter/X Fetcher (agent-browser)")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Tweets to fetch: {args.tweets}")
    print(f"Scroll count: {args.scrolls}")
    print(f"Output directory: {output_dir.absolute()}")
    print(f"Headed mode: {args.headed}")
    if args.use_chrome_profile or args.chrome_profile_path:
        print(f"{Colors.GREEN}Chrome Profile: Enabled (using existing logins){Colors.ENDC}")
        if args.chrome_profile_path:
            print(f"Profile path: {args.chrome_profile_path}")
    print()
    print(f"{Colors.CYAN}Using agent-browser (Vercel Labs){Colors.ENDC}")
    print(f"{Colors.CYAN}Features: Ref-based selection, Playwright/Chromium{Colors.ENDC}")

    results = []
    saved_files = []

    if args.all:
        models = ["gemini", "claude", "openai"]
        for model in models:
            print_header(f"Testing: {model.upper()}")
            try:
                result = await fetch_tweets_with_agentbrowser(
                    model, args.tweets, args.scrolls, args.headed,
                    args.use_chrome_profile, args.chrome_profile_path
                )
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
        result = await fetch_tweets_with_agentbrowser(
            args.model, args.tweets, args.scrolls, args.headed,
            args.use_chrome_profile, args.chrome_profile_path
        )
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
