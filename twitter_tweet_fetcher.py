"""
Twitter/X Tweet Fetcher Demo using Browser-Use

This demo compares different LLM models' ability to:
1. Open Twitter/X timeline using your logged-in Chrome profile
2. Fetch and extract tweet content from the timeline
3. Save tweets as structured Markdown

Supported LLM Models:
- ChatBrowserUse (Browser-Use Cloud)
- Google Gemini 2.5 Pro
- Claude Opus 4.5
- OpenAI GPT-5.2

Usage:
    uv run python twitter_tweet_fetcher.py --model <model_name>
    uv run python twitter_tweet_fetcher.py --all

Models:
    browser-use, gemini, claude, openai, all
"""

import asyncio
import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# macOS Chrome paths
CHROME_EXECUTABLE = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CHROME_USER_DATA_DIR = os.path.expanduser("~/Library/Application Support/Google/Chrome")
CHROME_PROFILE = "Default"

# Output directory for Markdown files
OUTPUT_DIR = Path("output")


class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


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


def get_llm(model_type: str):
    """Get the LLM instance based on model type."""
    if model_type == "browser-use":
        from browser_use import ChatBrowserUse
        api_key = os.getenv("BROWSER_USE_API_KEY")
        if not api_key:
            raise ValueError("BROWSER_USE_API_KEY environment variable is required")
        return ChatBrowserUse(), "Browser-Use Cloud"

    elif model_type == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        return ChatGoogleGenerativeAI(
            model="gemini-3-pro-preview",
            google_api_key=api_key,
            temperature=0.0
        ), "Google Gemini 3 Pro"

    elif model_type == "claude":
        from langchain_anthropic import ChatAnthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        return ChatAnthropic(
            model="claude-opus-4-5-20251101",
            anthropic_api_key=api_key,
            temperature=0.0
        ), "Claude Opus 4.5"

    elif model_type == "openai":
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        return ChatOpenAI(
            model="gpt-5.2",
            openai_api_key=api_key,
            temperature=0.0
        ), "OpenAI GPT-5.2"

    else:
        raise ValueError(f"Unknown model type: {model_type}")


def parse_tweets_from_output(raw_output: str) -> list[Tweet]:
    """
    Parse the raw LLM output into structured Tweet objects.
    The LLM is instructed to return JSON, but we handle fallback parsing.
    """
    tweets = []

    # Try to parse as JSON first
    try:
        # Look for JSON array in the output
        json_match = re.search(r'\[[\s\S]*\]', raw_output)
        if json_match:
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
            return tweets
    except json.JSONDecodeError:
        pass

    # Fallback: try to parse numbered format
    # Pattern: looks for tweet blocks separated by numbers or dashes
    tweet_blocks = re.split(r'\n(?=\d+[\.\):]|\-{3,}|Tweet #)', raw_output)

    for block in tweet_blocks:
        if not block.strip():
            continue

        # Extract author/handle
        author_match = re.search(r'@(\w+)', block)
        handle = f"@{author_match.group(1)}" if author_match else ""

        # Try to find author name
        name_match = re.search(r'(?:Author|Name|From):\s*([^\n@]+)', block, re.IGNORECASE)
        author = name_match.group(1).strip() if name_match else handle

        # Extract content
        content_match = re.search(r'(?:Content|Text|Tweet):\s*(.+?)(?=\n(?:Link|Likes|Retweets|$))', block, re.IGNORECASE | re.DOTALL)
        content = content_match.group(1).strip() if content_match else ""

        # If no content found, use the whole block minus metadata
        if not content:
            lines = block.strip().split('\n')
            content_lines = [l for l in lines if not re.match(r'^(Author|Name|Handle|Link|Likes|Retweets|Replies|@):', l, re.IGNORECASE)]
            content = ' '.join(content_lines).strip()

        # Extract link
        link_match = re.search(r'(?:Link|URL):\s*(https?://[^\s]+)', block, re.IGNORECASE)
        if not link_match:
            link_match = re.search(r'(https?://(?:twitter\.com|x\.com)/\w+/status/\d+)', block)
        link = link_match.group(1) if link_match else ""

        if content or author:
            tweets.append(Tweet(
                author=author or "Unknown",
                handle=handle,
                content=content,
                link=link,
            ))

    return tweets


def save_tweets_to_markdown(result: ModelResult, output_dir: Path) -> Path:
    """Save the tweets to a structured Markdown file."""
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_model_name = result.model_type.replace(" ", "_").replace("-", "_")
    filename = f"tweets_{safe_model_name}_{timestamp}.md"
    filepath = output_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Twitter/X Timeline Tweets\n\n")
        f.write(f"**Model:** {result.model_name}\n\n")
        f.write(f"**Fetched at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Execution time:** {result.execution_time:.2f} seconds\n\n")
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

                if tweet.likes or tweet.retweets or tweet.replies:
                    f.write(f"**Engagement:** ")
                    metrics = []
                    if tweet.likes:
                        metrics.append(f"{tweet.likes} likes")
                    if tweet.retweets:
                        metrics.append(f"{tweet.retweets} retweets")
                    if tweet.replies:
                        metrics.append(f"{tweet.replies} replies")
                    f.write(" | ".join(metrics) + "\n\n")

                f.write("---\n\n")
        else:
            f.write("*No tweets were extracted.*\n\n")
            if result.raw_output:
                f.write("## Raw Output\n\n")
                f.write("```\n")
                f.write(result.raw_output)
                f.write("\n```\n")

        if result.error_message:
            f.write(f"\n## Error\n\n")
            f.write(f"```\n{result.error_message}\n```\n")

    return filepath


async def fetch_tweets_with_model(model_type: str, num_tweets: int = 5) -> ModelResult:
    """Fetch tweets from Twitter/X timeline using the specified LLM model."""
    from browser_use import Agent, Browser

    start_time = time.time()
    result = ModelResult(model_name="", model_type=model_type)

    try:
        llm, model_name = get_llm(model_type)
        result.model_name = model_name
        print(f"{Colors.CYAN}[Model]{Colors.ENDC} {Colors.BOLD}{model_name}{Colors.ENDC}")

        print_info(f"Chrome: {CHROME_EXECUTABLE}")
        print_info(f"Profile: {CHROME_PROFILE}")
        print_info("Please close all Chrome windows before running...")

        browser = Browser(
            executable_path=CHROME_EXECUTABLE,
            user_data_dir=CHROME_USER_DATA_DIR,
            profile_directory=CHROME_PROFILE,
        )

        # Task instructs LLM to return structured JSON
        task = f"""
        Go to Twitter/X (https://x.com) and fetch tweets from the timeline.

        Instructions:
        1. Wait for the timeline to fully load (you should be logged in via Chrome profile)
        2. Scroll to see recent tweets
        3. Extract exactly {num_tweets} tweets

        For each tweet, extract:
        - author: The display name of the tweet author
        - handle: The @username (e.g., @elonmusk)
        - content: The full tweet text
        - link: The direct URL to the tweet (format: https://x.com/username/status/id)
        - likes: Number of likes (if visible)
        - retweets: Number of retweets (if visible)
        - timestamp: When the tweet was posted (if visible)

        IMPORTANT: Return the data as a JSON array like this:
        [
            {{
                "author": "Display Name",
                "handle": "@username",
                "content": "The tweet text...",
                "link": "https://x.com/username/status/123456789",
                "likes": 100,
                "retweets": 50,
                "timestamp": "2h"
            }}
        ]

        If you see a login page, report "LOGIN_REQUIRED" as an error.
        """

        agent = Agent(
            task=task,
            llm=llm,
            browser=browser,
        )

        print_info("Starting agent to fetch tweets...")
        history = await agent.run(max_steps=25)

        # Extract result from agent history
        raw_output = ""
        if history:
            if hasattr(history, 'final_result') and history.final_result:
                raw_output = history.final_result
            elif hasattr(history, 'result') and history.result:
                raw_output = str(history.result)
            elif hasattr(history, 'actions') and history.actions:
                for action in reversed(history.actions):
                    if hasattr(action, 'result') and action.result:
                        raw_output = str(action.result)
                        break

        result.raw_output = raw_output

        if raw_output:
            result.tweets = parse_tweets_from_output(raw_output)
            result.success = len(result.tweets) > 0
            if result.success:
                print_success(f"Extracted {len(result.tweets)} tweets")
            else:
                result.error_message = "Could not parse tweets from output"
                print_error(result.error_message)
        else:
            result.error_message = "No output from agent"
            print_error(result.error_message)

    except Exception as e:
        result.error_message = str(e)
        print_error(f"Failed: {e}")

    result.execution_time = time.time() - start_time
    return result


def print_result_summary(result: ModelResult) -> None:
    """Print a summary of the result."""
    print(f"\n{Colors.CYAN}Execution Time:{Colors.ENDC} {result.execution_time:.2f}s")
    print(f"{Colors.CYAN}Status:{Colors.ENDC} {'Success' if result.success else 'Failed'}")
    print(f"{Colors.CYAN}Tweets Found:{Colors.ENDC} {len(result.tweets)}")

    if result.tweets:
        print(f"\n{Colors.BOLD}Preview:{Colors.ENDC}")
        for i, tweet in enumerate(result.tweets[:3], 1):  # Show first 3
            content_preview = tweet.content[:80] + "..." if len(tweet.content) > 80 else tweet.content
            print(f"  {i}. {tweet.handle}: {content_preview}")
        if len(result.tweets) > 3:
            print(f"  ... and {len(result.tweets) - 3} more")


def print_comparison(results: list[ModelResult]) -> None:
    """Print a comparison table of all results."""
    print_header("Model Comparison")

    print(f"{'Model':<25} {'Status':<10} {'Time':<10} {'Tweets':<8}")
    print("-" * 55)

    for r in results:
        status = "OK" if r.success else "FAIL"
        print(f"{r.model_name:<25} {status:<10} {r.execution_time:<10.2f} {len(r.tweets):<8}")

    successful = [r for r in results if r.success]
    if successful:
        fastest = min(successful, key=lambda x: x.execution_time)
        most_tweets = max(successful, key=lambda x: len(x.tweets))
        print(f"\n{Colors.GREEN}Fastest:{Colors.ENDC} {fastest.model_name} ({fastest.execution_time:.2f}s)")
        print(f"{Colors.GREEN}Most tweets:{Colors.ENDC} {most_tweets.model_name} ({len(most_tweets.tweets)} tweets)")


async def main():
    parser = argparse.ArgumentParser(
        description="Fetch tweets from Twitter/X using different LLM models"
    )
    parser.add_argument(
        "--model",
        choices=["browser-use", "gemini", "claude", "openai"],
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
        "--output",
        type=str,
        default="output",
        help="Output directory for Markdown files (default: output)"
    )

    args = parser.parse_args()

    if not args.model and not args.all:
        parser.print_help()
        print(f"\n{Colors.YELLOW}Please specify --model <name> or --all{Colors.ENDC}")
        sys.exit(1)

    output_dir = Path(args.output)

    print_header("Twitter/X Tweet Fetcher")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Tweets to fetch: {args.tweets}")
    print(f"Output directory: {output_dir.absolute()}")

    results = []
    saved_files = []

    if args.all:
        models = ["browser-use", "gemini", "claude", "openai"]
        for model in models:
            print_header(f"Testing: {model.upper()}")
            try:
                result = await fetch_tweets_with_model(model, args.tweets)
                results.append(result)
                print_result_summary(result)

                # Save to Markdown
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
        result = await fetch_tweets_with_model(args.model, args.tweets)
        results.append(result)
        print_result_summary(result)

        filepath = save_tweets_to_markdown(result, output_dir)
        saved_files.append(filepath)
        print_success(f"Saved to: {filepath}")

    # Summary of saved files
    if saved_files:
        print_header("Output Files")
        for f in saved_files:
            print(f"  - {f}")

    return results


def main_cli():
    """Entry point for the CLI."""
    asyncio.run(main())


if __name__ == "__main__":
    main_cli()
