"""
Browser-Use Demo: Fetch Tweets from X.com

This demo uses the browser-use library with ChatBrowserUse() LLM to:
1. Open Chrome browser with your default profile (using existing login sessions)
2. Navigate to x.com
3. Fetch tweet contents from your timeline

Prerequisites:
    1. Set BROWSER_USE_API_KEY environment variable (get from https://browser-use.com)
    2. Close all Chrome windows before running (browser-use needs exclusive access)
    3. Install dependencies: uv sync

Usage:
    # Set API key first
    export BROWSER_USE_API_KEY=your-api-key

    # Run the demo
    uv run python browser_use_demo.py

Note: This uses your default Chrome profile, so you should already be logged into X.com.
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def check_api_key() -> str:
    """Check that BROWSER_USE_API_KEY is set."""
    api_key = os.getenv("BROWSER_USE_API_KEY")
    if not api_key:
        print("Error: BROWSER_USE_API_KEY environment variable is required.")
        print("")
        print("To get an API key:")
        print("  1. Visit https://browser-use.com")
        print("  2. Sign up for an account (new users get $10 free credits)")
        print("  3. Copy your API key")
        print("")
        print("Then set the environment variable:")
        print("  export BROWSER_USE_API_KEY=your-api-key")
        print("")
        print("Or add it to your .env file:")
        print("  echo 'BROWSER_USE_API_KEY=your-api-key' >> .env")
        sys.exit(1)
    return api_key


async def fetch_tweets():
    """Fetch tweets from X.com using browser-use with ChatBrowserUse."""
    # Import browser-use components
    from browser_use import Agent, Browser, ChatBrowserUse

    # Check API key is set
    check_api_key()

    print("=" * 60)
    print("Browser-Use Demo: Fetching Tweets from X.com")
    print("=" * 60)
    print("")

    # Configure Chrome browser with your default profile
    # This allows using your existing login session
    print("[INFO] Configuring Chrome browser with default profile...")
    print("[INFO] Make sure all Chrome windows are closed before running!")
    print("")

    # macOS Chrome paths
    chrome_executable = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    chrome_user_data = os.path.expanduser("~/Library/Application Support/Google/Chrome")

    # Create browser instance with Chrome profile
    browser = Browser(
        executable_path=chrome_executable,
        user_data_dir=chrome_user_data,
        profile_directory="Default",  # Use "Default" profile or specify your profile name
    )

    # Create LLM using ChatBrowserUse (optimized for browser automation)
    # This uses BROWSER_USE_API_KEY from environment
    print("[INFO] Initializing ChatBrowserUse LLM...")
    llm = ChatBrowserUse()

    # Define the task for fetching tweets
    task = """
    Navigate to https://x.com and fetch the contents of the first 5 tweets from the timeline.

    Steps:
    1. Go to x.com
    2. Wait for the page to load completely
    3. Scroll down slightly to ensure tweets are loaded
    4. Extract the following information for each of the first 5 tweets:
       - Author name
       - Author handle (@username)
       - Tweet content/text
       - Timestamp if visible
    5. Return the tweets as a formatted list

    If you encounter a login page, note that we're using the default Chrome profile
    which should have existing login sessions. Wait a moment for the page to load.
    """

    print(f"[INFO] Task: Fetch tweets from X.com timeline")
    print("[INFO] Starting browser automation...")
    print("")

    # Create and run the agent
    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
    )

    try:
        # Run the agent
        history = await agent.run()

        print("")
        print("=" * 60)
        print("RESULTS")
        print("=" * 60)
        print("")

        # Check if the task was successful
        if history.is_successful():
            print("[SUCCESS] Agent completed the task successfully!")
        else:
            print("[WARNING] Agent completed but may not have fully succeeded")

        # Print execution stats
        print(f"[INFO] Total steps: {history.number_of_steps()}")
        print(f"[INFO] Duration: {history.total_duration_seconds():.2f} seconds")
        print("")

        # Extract the final result
        result = history.final_result()
        if result:
            print("Fetched Tweets:")
            print("-" * 40)
            print(result)
        else:
            # Try extracted content as fallback
            extracted = history.extracted_content()
            if extracted:
                print("Extracted Content:")
                print("-" * 40)
                for content in extracted:
                    print(content)
            else:
                print("[INFO] No result extracted. Showing model outputs...")
                outputs = history.model_outputs()
                for output in outputs[-3:]:  # Show last 3 outputs
                    print(output)

        # Check for any errors
        if history.has_errors():
            print("")
            print("[ERRORS] The following errors occurred:")
            for error in history.errors():
                print(f"  - {error}")

    except Exception as e:
        print(f"[ERROR] Agent execution failed: {e}")
        raise
    finally:
        # Clean up browser
        print("")
        print("[INFO] Closing browser...")
        await browser.close()
        print("[INFO] Done!")


async def main():
    """Main entry point."""
    await fetch_tweets()


if __name__ == "__main__":
    asyncio.run(main())
