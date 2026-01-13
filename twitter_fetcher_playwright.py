"""
Twitter/X Tweet Fetcher using pycookiecheat + Playwright

This implementation uses:
- pycookiecheat: Extracts cookies from Chrome without needing to close it
- Playwright: Modern browser automation with full Python control

Key Advantages:
- No need to close Chrome - cookies extracted from browser's SQLite database
- No profile lock issues - uses a separate browser instance with injected cookies
- Full Playwright API - direct control without MCP protocol overhead
- Real session cookies - authenticated access, avoids bot detection

Supported Modes:
- Direct mode: Use Playwright selectors directly for fast, reliable extraction
- LLM mode: LLM decides navigation/extraction steps (Claude, Gemini, OpenAI)

Usage:
    uv run python twitter_fetcher_playwright.py --mode direct --tweets 5
    uv run python twitter_fetcher_playwright.py --mode llm --model claude --tweets 5
"""

import argparse
import asyncio
import base64
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, cast

from dotenv import load_dotenv

load_dotenv()

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
    log_file = LOG_DIR / f"playwright_{timestamp}.log"

    logger = logging.getLogger("playwright")
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
    console_formatter = logging.Formatter(f"{Colors.BLUE}[Playwright]{Colors.ENDC} %(message)s")
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


def get_twitter_cookies() -> dict[str, str]:
    """Extract Twitter/X cookies from Chrome browser."""
    try:
        from pycookiecheat import chrome_cookies
    except ImportError:
        raise ImportError("pycookiecheat is required. Install with: pip install pycookiecheat")

    # Try both twitter.com and x.com domains
    cookies = {}
    for domain in ["https://twitter.com", "https://x.com"]:
        try:
            domain_cookies = chrome_cookies(domain)
            cookies.update(domain_cookies)
        except Exception as e:
            if logger:
                logger.debug(f"Could not get cookies for {domain}: {e}")

    if not cookies:
        raise RuntimeError(
            "No Twitter/X cookies found in Chrome. "
            "Make sure you're logged into Twitter/X in Chrome."
        )

    return cookies


def convert_cookies_for_playwright(cookies: dict[str, str], domain: str = ".x.com") -> list[dict]:
    """Convert cookies dict to Playwright cookie format."""
    playwright_cookies = []
    for name, value in cookies.items():
        playwright_cookies.append({
            "name": name,
            "value": value,
            "domain": domain,
            "path": "/",
        })
    return playwright_cookies


async def setup_browser_with_cookies(cookies: dict[str, str], headless: bool = False):
    """Launch Playwright browser and inject cookies."""
    from playwright.async_api import async_playwright

    playwright = await async_playwright().start()

    # Launch Chromium browser (headed mode by default)
    browser = await playwright.chromium.launch(headless=headless)

    # Create context with cookies
    context = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )

    # Add cookies for both domains
    all_cookies = []
    for domain in [".x.com", ".twitter.com"]:
        all_cookies.extend(convert_cookies_for_playwright(cookies, domain))

    await context.add_cookies(all_cookies)

    page = await context.new_page()
    return playwright, browser, context, page


def get_tweet_extraction_js(num_tweets: int = 5) -> str:
    """JavaScript code to extract tweets from Twitter DOM."""
    return f"""
() => {{
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
    return tweets;
}}
"""


async def extract_tweets_direct(page, num_tweets: int = 5, num_scrolls: int = 3) -> list[Tweet]:
    """Extract tweets directly using Playwright without LLM."""
    if logger:
        logger.info(f"Navigating to Twitter/X...")

    # Navigate to Twitter home (use domcontentloaded - networkidle times out on Twitter)
    await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=60000)

    # Wait for tweets to appear (this is more reliable than networkidle)
    if logger:
        logger.info("Waiting for tweets to load...")
    try:
        await page.wait_for_selector('article[data-testid="tweet"]', timeout=30000)
    except Exception:
        if logger:
            logger.warning("Tweets not found yet, waiting longer...")
        await page.wait_for_timeout(5000)

    if logger:
        logger.info(f"Page loaded. Scrolling {num_scrolls} times to load more tweets...")

    # Scroll to load more tweets
    for i in range(num_scrolls):
        await page.keyboard.press("PageDown")
        await page.wait_for_timeout(2000)
        if logger:
            logger.info(f"Scroll {i + 1}/{num_scrolls} completed")

    # Final wait for any lazy-loaded content
    await page.wait_for_timeout(1000)

    # Extract tweets using JavaScript
    js_code = get_tweet_extraction_js(num_tweets)
    raw_tweets = await page.evaluate(js_code)

    tweets = []
    for item in raw_tweets:
        tweet = Tweet(
            author=item.get("author", "Unknown"),
            handle=item.get("handle", ""),
            content=item.get("content", ""),
            link=item.get("link", ""),
            timestamp=item.get("timestamp"),
        )
        tweets.append(tweet)

    return tweets


class PlaywrightTools:
    """Wrapper class that exposes Playwright actions as callable tools for LLM."""

    def __init__(self, page):
        self.page = page
        self.tool_calls_count = 0

    def get_tool_definitions(self) -> list[dict]:
        """Get tool definitions for LLM."""
        return [
            {
                "name": "navigate",
                "description": "Navigate to a URL",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "The URL to navigate to"}
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "click",
                "description": "Click on an element matching the selector",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string", "description": "CSS selector of element to click"}
                    },
                    "required": ["selector"]
                }
            },
            {
                "name": "type_text",
                "description": "Type text into an input field",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string", "description": "CSS selector of input element"},
                        "text": {"type": "string", "description": "Text to type"}
                    },
                    "required": ["selector", "text"]
                }
            },
            {
                "name": "press_key",
                "description": "Press a keyboard key (e.g., Enter, PageDown, Escape)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Key to press (e.g., 'PageDown', 'Enter')"}
                    },
                    "required": ["key"]
                }
            },
            {
                "name": "scroll",
                "description": "Scroll the page up or down",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "direction": {"type": "string", "enum": ["up", "down"], "description": "Direction to scroll"}
                    },
                    "required": ["direction"]
                }
            },
            {
                "name": "wait",
                "description": "Wait for a specified duration in milliseconds",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "duration": {"type": "integer", "description": "Duration to wait in milliseconds"}
                    },
                    "required": ["duration"]
                }
            },
            {
                "name": "get_page_content",
                "description": "Get the text content of the current page",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "extract_tweets",
                "description": "Extract tweets from the current Twitter/X page",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "count": {"type": "integer", "description": "Number of tweets to extract", "default": 5}
                    }
                }
            },
            {
                "name": "screenshot",
                "description": "Take a screenshot of the current page",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
        ]

    async def call_tool(self, name: str, arguments: dict) -> str:
        """Call a tool by name with arguments."""
        self.tool_calls_count += 1

        if name == "navigate":
            url = arguments.get("url", "")
            await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            return f"Navigated to {url}"

        elif name == "click":
            selector = arguments.get("selector", "")
            await self.page.click(selector)
            return f"Clicked on {selector}"

        elif name == "type_text":
            selector = arguments.get("selector", "")
            text = arguments.get("text", "")
            await self.page.fill(selector, text)
            return f"Typed text into {selector}"

        elif name == "press_key":
            key = arguments.get("key", "")
            await self.page.keyboard.press(key)
            return f"Pressed key {key}"

        elif name == "scroll":
            direction = arguments.get("direction", "down")
            key = "PageDown" if direction == "down" else "PageUp"
            await self.page.keyboard.press(key)
            return f"Scrolled {direction}"

        elif name == "wait":
            duration = arguments.get("duration", 1000)
            await self.page.wait_for_timeout(duration)
            return f"Waited {duration}ms"

        elif name == "get_page_content":
            content = await self.page.content()
            # Return truncated content to avoid token limits
            return content[:8000]

        elif name == "extract_tweets":
            count = arguments.get("count", 5)
            js_code = get_tweet_extraction_js(count)
            tweets = await self.page.evaluate(js_code)
            return json.dumps(tweets, indent=2)

        elif name == "screenshot":
            screenshot_bytes = await self.page.screenshot()
            # Return base64 encoded screenshot
            b64 = base64.b64encode(screenshot_bytes).decode()
            return f"Screenshot taken (base64 length: {len(b64)})"

        else:
            return f"Unknown tool: {name}"


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


async def run_with_llm(tools: PlaywrightTools, model_type: str, num_tweets: int, num_scrolls: int) -> tuple[list[Tweet], str]:
    """Run tweet extraction with LLM guidance."""
    task = f"""You are a browser automation agent. Complete this task using the available tools:

1. Navigate to Twitter/X home page using navigate with url "https://x.com/home"
2. Wait for the page to load (use wait with duration 3000)
3. Scroll down {num_scrolls} times to load more tweets:
   - Use press_key with key "PageDown" or scroll with direction "down"
   - Wait 2000ms after each scroll
4. Extract {num_tweets} tweets using the extract_tweets tool
5. Return the extracted tweets as your final response

The user is already logged in via cookies. Just navigate and extract the tweets.

IMPORTANT: After calling extract_tweets, include the JSON result in your final text response.
"""

    if model_type == "claude":
        return await _run_with_claude(tools, task)
    elif model_type == "gemini":
        return await _run_with_gemini(tools, task)
    elif model_type == "openai":
        return await _run_with_openai(tools, task)
    else:
        raise ValueError(f"Unknown model type: {model_type}")


async def _run_with_claude(tools: PlaywrightTools, task: str, max_steps: int = 20) -> tuple[list[Tweet], str]:
    """Run task using Claude with tool use."""
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")

    client = anthropic.Anthropic(api_key=api_key)

    # Convert tools to Anthropic format
    tool_defs = tools.get_tool_definitions()
    anthropic_tools = []
    for t in tool_defs:
        anthropic_tools.append({
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["parameters"],
        })

    messages: list[Any] = [{"role": "user", "content": task}]
    final_result = ""

    for step in range(max_steps):
        if logger:
            logger.info(f"Step {step + 1}/{max_steps}")

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            tools=anthropic_tools,  # type: ignore
            messages=messages,  # type: ignore
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

            try:
                result = await tools.call_tool(tool_name, tool_args)
            except Exception as e:
                result = f"Error: {str(e)}"

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result[:10000]
            })

        messages.append({"role": "user", "content": tool_results})

        if response.stop_reason == "end_turn":
            break

    # Parse tweets from final result
    tweets = parse_tweets_from_json(final_result)
    return tweets, final_result


async def _run_with_gemini(tools: PlaywrightTools, task: str, max_steps: int = 20) -> tuple[list[Tweet], str]:
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

    # Convert tools to Gemini function declarations
    tool_defs = tools.get_tool_definitions()
    function_declarations = []
    for t in tool_defs:
        params = clean_schema_for_gemini(t["parameters"])
        function_declarations.append(genai_types.FunctionDeclaration(
            name=t["name"],
            description=t["description"],
            parameters=params,
        ))

    chat = client.aio.chats.create(
        model="gemini-2.0-flash",
        config=genai_types.GenerateContentConfig(
            tools=[genai_types.Tool(function_declarations=function_declarations)],
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

            try:
                result = await tools.call_tool(tool_name, tool_args)
            except Exception as e:
                result = f"Error: {str(e)}"

            if logger:
                logger.info(f"Tool {tool_name} result: {result[:200]}...")

            function_responses.append(genai_types.Part.from_function_response(
                name=tool_name,
                response={"result": result[:8000]}
            ))

        response = await chat.send_message(function_responses)

    tweets = parse_tweets_from_json(final_result)
    return tweets, final_result


async def _run_with_openai(tools: PlaywrightTools, task: str, max_steps: int = 20) -> tuple[list[Tweet], str]:
    """Run task using OpenAI with function calling."""
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")

    client = OpenAI(api_key=api_key)

    # Convert tools to OpenAI format
    tool_defs = tools.get_tool_definitions()
    openai_tools = []
    for t in tool_defs:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            }
        })

    messages: list[Any] = [{"role": "user", "content": task}]
    final_result = ""

    for step in range(max_steps):
        if logger:
            logger.info(f"Step {step + 1}/{max_steps}")

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,  # type: ignore
            tools=openai_tools,  # type: ignore
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

            try:
                result = await tools.call_tool(tool_name, tool_args)
            except Exception as e:
                result = f"Error: {str(e)}"

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result[:10000]
            })

    tweets = parse_tweets_from_json(final_result)
    return tweets, final_result


def parse_tweets_from_json(raw_output: str) -> list[Tweet]:
    """Parse tweets from JSON output."""
    import re

    tweets = []

    # Try to find JSON in code blocks
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
    filename = f"tweets_playwright_{safe_model_name}_{timestamp}.md"
    filepath = output_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Twitter/X Timeline Tweets (Playwright + pycookiecheat)\n\n")
        f.write(f"**Model:** {result.model_name}\n\n")
        f.write(f"**Method:** pycookiecheat + Playwright\n\n")
        f.write(f"**Fetched at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Execution time:** {result.execution_time:.2f} seconds\n\n")
        if result.tool_calls_count > 0:
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


async def fetch_tweets_direct(num_tweets: int = 5, num_scrolls: int = 3) -> ModelResult:
    """Fetch tweets using direct Playwright extraction (no LLM)."""
    start_time = time.time()
    result = ModelResult(model_name="Direct (No LLM)", model_type="direct")

    print(f"{Colors.CYAN}[Mode]{Colors.ENDC} {Colors.BOLD}Direct Extraction (Playwright){Colors.ENDC}")
    print_info("Using pycookiecheat + Playwright - no LLM required")
    print_info("No need to close Chrome! Cookies extracted from browser database.")

    try:
        # Extract cookies
        print_info("Extracting cookies from Chrome...")
        cookies = get_twitter_cookies()
        print_success(f"Found {len(cookies)} cookies")

        # Setup browser
        print_info("Launching Playwright browser with cookies...")
        playwright, browser, context, page = await setup_browser_with_cookies(cookies)

        try:
            # Extract tweets
            print_info(f"Extracting {num_tweets} tweets...")
            result.tweets = await extract_tweets_direct(page, num_tweets, num_scrolls)
            result.success = len(result.tweets) > 0

            if result.success:
                print_success(f"Extracted {len(result.tweets)} tweets")
            else:
                result.error_message = "No tweets extracted"
                print_error(result.error_message)

        finally:
            await browser.close()
            await playwright.stop()

    except Exception as e:
        result.error_message = str(e)
        print_error(f"Failed: {e}")
        if logger:
            logger.exception("Error during execution")

    result.execution_time = time.time() - start_time
    return result


async def fetch_tweets_with_llm(model_type: str, num_tweets: int = 5, num_scrolls: int = 3) -> ModelResult:
    """Fetch tweets using LLM-guided Playwright automation."""
    start_time = time.time()
    result = ModelResult(model_name="", model_type=model_type)

    model_names = {
        "gemini": "Google Gemini 2.0 Flash",
        "claude": "Claude Sonnet 4",
        "openai": "OpenAI GPT-4o",
    }
    result.model_name = model_names.get(model_type, model_type)

    print(f"{Colors.CYAN}[Model]{Colors.ENDC} {Colors.BOLD}{result.model_name}{Colors.ENDC}")
    print_info("Using pycookiecheat + Playwright with LLM guidance")
    print_info("No need to close Chrome! Cookies extracted from browser database.")

    try:
        # Extract cookies
        print_info("Extracting cookies from Chrome...")
        cookies = get_twitter_cookies()
        print_success(f"Found {len(cookies)} cookies")

        # Setup browser
        print_info("Launching Playwright browser with cookies...")
        playwright, browser, context, page = await setup_browser_with_cookies(cookies)

        try:
            # Create tools wrapper
            tools = PlaywrightTools(page)

            # Run with LLM
            print_info("Starting LLM orchestration...")
            result.tweets, result.raw_output = await run_with_llm(tools, model_type, num_tweets, num_scrolls)
            result.tool_calls_count = tools.tool_calls_count
            result.success = len(result.tweets) > 0

            if result.success:
                print_success(f"Extracted {len(result.tweets)} tweets in {tools.tool_calls_count} tool calls")
            else:
                result.error_message = "Could not parse tweets from output"
                print_error(result.error_message)

        finally:
            await browser.close()
            await playwright.stop()

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
    if result.tool_calls_count > 0:
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


async def main():
    parser = argparse.ArgumentParser(
        description="Fetch tweets using pycookiecheat + Playwright"
    )
    parser.add_argument(
        "--mode",
        choices=["direct", "llm"],
        required=True,
        help="Extraction mode: 'direct' for Playwright-only, 'llm' for LLM-guided"
    )
    parser.add_argument(
        "--model",
        choices=["gemini", "claude", "openai"],
        help="LLM model to use (required for llm mode)"
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

    args = parser.parse_args()

    if args.mode == "llm" and not args.model:
        parser.error("--model is required when using --mode llm")

    output_dir = Path(args.output)

    global logger
    logger = setup_logging(args.log_level)

    print_header("Twitter/X Fetcher (Playwright + pycookiecheat)")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {args.mode}")
    if args.model:
        print(f"Model: {args.model}")
    print(f"Tweets to fetch: {args.tweets}")
    print(f"Scroll count: {args.scrolls}")
    print(f"Output directory: {output_dir.absolute()}")
    print()
    print(f"{Colors.GREEN}Advantage: No need to close Chrome!{Colors.ENDC}")
    print(f"{Colors.GREEN}Cookies extracted from Chrome's database.{Colors.ENDC}")

    if args.mode == "direct":
        result = await fetch_tweets_direct(args.tweets, args.scrolls)
    else:
        result = await fetch_tweets_with_llm(args.model, args.tweets, args.scrolls)

    print_result_summary(result)

    filepath = save_tweets_to_markdown(result, output_dir)
    print_success(f"Saved to: {filepath}")

    print_header("Output Files")
    print(f"  - {filepath}")

    return result


if __name__ == "__main__":
    asyncio.run(main())
