"""
Twitter/X Tweet Fetcher Demo using Browser-Use

This demo compares different LLM models' ability to:
1. Open Twitter/X timeline using your logged-in Chrome profile
2. Fetch and extract tweet content from the timeline
3. Print out the tweets for evaluation

Supported LLM Models:
- ChatBrowserUse (Browser-Use Cloud)
- Google Gemini 2.5 Pro
- Claude Opus 4.5
- OpenAI GPT-5.2

Usage:
    python twitter_tweet_fetcher.py --model <model_name>
    python twitter_tweet_fetcher.py --all  # Run all models sequentially for comparison

Models:
    browser-use, gemini, claude, openai, all
"""

import asyncio
import argparse
import os
import platform
import sys
import time
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Color codes for terminal output
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
class ModelResult:
    """Stores the result of running a model"""
    model_name: str
    tweets: list[str]
    execution_time: float
    success: bool
    error_message: Optional[str] = None


def get_chrome_paths() -> tuple[str, str, str]:
    """Get Chrome executable path, user data dir, and profile based on OS"""
    system = platform.system()

    if system == "Darwin":  # macOS
        executable = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        user_data_dir = os.path.expanduser("~/Library/Application Support/Google/Chrome")
        profile = "Default"
    elif system == "Windows":
        # Common Windows paths
        executable = os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe")
        if not os.path.exists(executable):
            executable = os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe")
        if not os.path.exists(executable):
            executable = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
        user_data_dir = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
        profile = "Default"
    else:  # Linux
        executable = "/usr/bin/google-chrome"
        if not os.path.exists(executable):
            executable = "/usr/bin/chromium-browser"
        if not os.path.exists(executable):
            executable = "/usr/bin/chromium"
        user_data_dir = os.path.expanduser("~/.config/google-chrome")
        if not os.path.exists(user_data_dir):
            user_data_dir = os.path.expanduser("~/.config/chromium")
        profile = "Default"

    return executable, user_data_dir, profile


def print_header(text: str) -> None:
    """Print a styled header"""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.ENDC}\n")


def print_model_info(model_name: str) -> None:
    """Print model information"""
    print(f"{Colors.CYAN}[Model]{Colors.ENDC} {Colors.BOLD}{model_name}{Colors.ENDC}")


def print_tweet(index: int, content: str) -> None:
    """Print a single tweet"""
    print(f"\n{Colors.GREEN}--- Tweet #{index} ---{Colors.ENDC}")
    print(content)


def print_error(message: str) -> None:
    """Print error message"""
    print(f"{Colors.RED}[ERROR]{Colors.ENDC} {message}")


def print_success(message: str) -> None:
    """Print success message"""
    print(f"{Colors.GREEN}[SUCCESS]{Colors.ENDC} {message}")


def get_llm(model_type: str):
    """
    Get the LLM instance based on model type.

    Args:
        model_type: One of 'browser-use', 'gemini', 'claude', 'openai'

    Returns:
        LLM instance configured for the specified model
    """
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

        # Using Gemini 2.5 Pro - the latest stable version
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-pro",
            google_api_key=api_key,
            temperature=0.0
        ), "Google Gemini 2.5 Pro"

    elif model_type == "claude":
        from langchain_anthropic import ChatAnthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        # Using Claude Opus 4.5
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

        # Using GPT-5.2
        return ChatOpenAI(
            model="gpt-5.2",
            openai_api_key=api_key,
            temperature=0.0
        ), "OpenAI GPT-5.2"

    else:
        raise ValueError(f"Unknown model type: {model_type}")


async def fetch_tweets_with_model(model_type: str, num_tweets: int = 5) -> ModelResult:
    """
    Fetch tweets from Twitter/X timeline using the specified LLM model.

    Args:
        model_type: The type of model to use
        num_tweets: Number of tweets to fetch (default 5)

    Returns:
        ModelResult containing the fetched tweets and execution info
    """
    from browser_use import Agent, Browser

    start_time = time.time()
    tweets = []
    error_message = None
    success = False

    try:
        # Get LLM instance
        llm, model_name = get_llm(model_type)
        print_model_info(model_name)

        # Get Chrome paths for the current OS
        executable, user_data_dir, profile = get_chrome_paths()

        print(f"{Colors.YELLOW}[INFO]{Colors.ENDC} Chrome executable: {executable}")
        print(f"{Colors.YELLOW}[INFO]{Colors.ENDC} User data dir: {user_data_dir}")
        print(f"{Colors.YELLOW}[INFO]{Colors.ENDC} Profile: {profile}")
        print(f"{Colors.YELLOW}[INFO]{Colors.ENDC} Please close all Chrome windows before running...")

        # Create browser with user's Chrome profile
        browser = Browser(
            executable_path=executable,
            user_data_dir=user_data_dir,
            profile_directory=profile,
        )

        # Define the task for fetching tweets
        task = f"""
        Go to Twitter/X (https://x.com or https://twitter.com) and:
        1. Wait for the timeline to fully load (you should be logged in via the Chrome profile)
        2. Scroll through the timeline to see recent tweets
        3. Extract the content of the first {num_tweets} tweets you see
        4. For each tweet, include:
           - The author's name/handle
           - The tweet text content
           - Any engagement metrics visible (likes, retweets, replies) if easily accessible
        5. Return the tweets in a clear, numbered format

        If you encounter a login page, the Chrome profile may not be logged in - report this as an error.
        """

        # Create and run the agent
        agent = Agent(
            task=task,
            llm=llm,
            browser=browser,
        )

        print(f"{Colors.YELLOW}[INFO]{Colors.ENDC} Starting agent to fetch tweets...")

        # Run the agent with a reasonable step limit
        history = await agent.run(max_steps=20)

        # Extract the final result from agent history
        if history and hasattr(history, 'final_result'):
            result_text = history.final_result
            if result_text:
                # Parse tweets from the result
                tweets = [result_text]  # Store the full result for now
                success = True
                print_success(f"Successfully fetched tweets using {model_name}")
        else:
            # Try to get result from the last action
            if history and hasattr(history, 'actions') and history.actions:
                last_action = history.actions[-1]
                if hasattr(last_action, 'result'):
                    tweets = [str(last_action.result)]
                    success = True

            if not success:
                error_message = "No tweets found in agent response"
                print_error(error_message)

    except Exception as e:
        error_message = str(e)
        print_error(f"Failed to fetch tweets: {error_message}")

    execution_time = time.time() - start_time

    return ModelResult(
        model_name=model_name if 'model_name' in dir() else model_type,
        tweets=tweets,
        execution_time=execution_time,
        success=success,
        error_message=error_message
    )


def print_result(result: ModelResult) -> None:
    """Print the result of a model run"""
    print_header(f"Results: {result.model_name}")

    print(f"{Colors.CYAN}Execution Time:{Colors.ENDC} {result.execution_time:.2f} seconds")
    print(f"{Colors.CYAN}Status:{Colors.ENDC} {'Success' if result.success else 'Failed'}")

    if result.error_message:
        print(f"{Colors.CYAN}Error:{Colors.ENDC} {result.error_message}")

    if result.tweets:
        print(f"\n{Colors.BOLD}Fetched Content:{Colors.ENDC}")
        for i, tweet in enumerate(result.tweets, 1):
            print_tweet(i, tweet)
    else:
        print(f"\n{Colors.YELLOW}No tweets were fetched{Colors.ENDC}")


def print_comparison(results: list[ModelResult]) -> None:
    """Print a comparison of all model results"""
    print_header("Model Comparison Summary")

    print(f"{'Model':<25} {'Status':<10} {'Time (s)':<12} {'Tweets':<10}")
    print("-" * 60)

    for result in results:
        status = "Success" if result.success else "Failed"
        tweet_count = len(result.tweets) if result.tweets else 0
        print(f"{result.model_name:<25} {status:<10} {result.execution_time:<12.2f} {tweet_count:<10}")

    # Find the best performing model
    successful_results = [r for r in results if r.success]
    if successful_results:
        fastest = min(successful_results, key=lambda x: x.execution_time)
        print(f"\n{Colors.GREEN}Fastest successful model:{Colors.ENDC} {fastest.model_name} ({fastest.execution_time:.2f}s)")


async def main():
    parser = argparse.ArgumentParser(
        description="Fetch tweets from Twitter/X using different LLM models via browser-use"
    )
    parser.add_argument(
        "--model",
        choices=["browser-use", "gemini", "claude", "openai"],
        help="LLM model to use for fetching tweets"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all models sequentially for comparison"
    )
    parser.add_argument(
        "--tweets",
        type=int,
        default=5,
        help="Number of tweets to fetch (default: 5)"
    )

    args = parser.parse_args()

    if not args.model and not args.all:
        parser.print_help()
        print(f"\n{Colors.YELLOW}Please specify --model <model_name> or --all{Colors.ENDC}")
        sys.exit(1)

    print_header("Twitter/X Tweet Fetcher Demo")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Tweets to fetch: {args.tweets}")

    results = []

    if args.all:
        # Run all models
        models = ["browser-use", "gemini", "claude", "openai"]
        for model in models:
            print_header(f"Testing: {model.upper()}")
            try:
                result = await fetch_tweets_with_model(model, args.tweets)
                results.append(result)
                print_result(result)
            except ValueError as e:
                print_error(f"Skipping {model}: {str(e)}")
                results.append(ModelResult(
                    model_name=model,
                    tweets=[],
                    execution_time=0,
                    success=False,
                    error_message=str(e)
                ))
            print("\n" + "="*60 + "\n")

        # Print comparison
        print_comparison(results)
    else:
        # Run single model
        result = await fetch_tweets_with_model(args.model, args.tweets)
        results.append(result)
        print_result(result)

    return results


if __name__ == "__main__":
    asyncio.run(main())
