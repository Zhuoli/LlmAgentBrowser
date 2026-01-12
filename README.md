# LLM Browser Agent Demo - Twitter/X Tweet Fetcher

A demo project to evaluate different LLM models using [browser-use](https://github.com/browser-use/browser-use) for autonomous web browsing. This project fetches tweets from Twitter/X timeline using your logged-in Chrome profile.

## Supported LLM Models

| Model | Provider | Model ID |
|-------|----------|----------|
| ChatBrowserUse | Browser-Use Cloud | Built-in |
| Gemini 2.5 Pro | Google | `gemini-2.5-pro` |
| Claude Opus 4.5 | Anthropic | `claude-opus-4-5-20251101` |
| GPT-5.2 | OpenAI | `gpt-5.2` |

## Prerequisites

- Python >= 3.11
- Google Chrome browser (with your Twitter/X account logged in)
- API keys for the LLM providers you want to test

## Installation

1. Clone this repository:
```bash
git clone <repo-url>
cd LlmAgentBrowser
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install browser-use CLI tools:
```bash
uvx browser-use install
```

5. Set up your environment variables:
```bash
cp .env.example .env
# Edit .env and add your API keys
```

## Configuration

Edit the `.env` file with your API keys:

```env
BROWSER_USE_API_KEY=your-browser-use-api-key
GOOGLE_API_KEY=your-google-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
OPENAI_API_KEY=your-openai-api-key
```

### Getting API Keys

- **Browser-Use Cloud**: https://cloud.browser-use.com/new-api-key
- **Google Gemini**: https://aistudio.google.com/apikey
- **Anthropic Claude**: https://console.anthropic.com/
- **OpenAI**: https://platform.openai.com/api-keys

## Usage

**Important**: Close all Chrome browser windows before running the script, as browser-use needs exclusive access to your Chrome profile.

### Test a single model:

```bash
# Using Browser-Use Cloud
python twitter_tweet_fetcher.py --model browser-use

# Using Google Gemini
python twitter_tweet_fetcher.py --model gemini

# Using Claude Opus 4.5
python twitter_tweet_fetcher.py --model claude

# Using OpenAI GPT-5.2
python twitter_tweet_fetcher.py --model openai
```

### Test all models for comparison:

```bash
python twitter_tweet_fetcher.py --all
```

### Customize number of tweets to fetch:

```bash
python twitter_tweet_fetcher.py --model gemini --tweets 10
```

## How It Works

1. **Browser Connection**: The script connects to Chrome using your default profile (where you're logged into Twitter/X)
2. **Agent Execution**: The LLM agent navigates to Twitter/X, waits for the timeline to load
3. **Tweet Extraction**: The agent extracts tweet content including author, text, and engagement metrics
4. **Results Display**: Tweets are printed with timing information for model comparison

## Output Example

```
============================================================
          Twitter/X Tweet Fetcher Demo
============================================================

Timestamp: 2025-01-11 10:30:45
Tweets to fetch: 5

[Model] Google Gemini 2.5 Pro
[INFO] Chrome executable: /usr/bin/google-chrome
[INFO] Starting agent to fetch tweets...
[SUCCESS] Successfully fetched tweets using Google Gemini 2.5 Pro

============================================================
          Results: Google Gemini 2.5 Pro
============================================================

Execution Time: 45.32 seconds
Status: Success

Fetched Content:
--- Tweet #1 ---
@user1: Just shipped a new feature!
Likes: 234 | Retweets: 45

...
```

## Troubleshooting

### "Chrome profile not found"
- Ensure Chrome is installed in the default location
- Check that your Chrome profile path is correct for your OS

### "Login required"
- Make sure you're logged into Twitter/X in your Chrome browser before running
- The script uses your existing session cookies from the Chrome profile

### "Browser already in use"
- Close all Chrome windows before running the script
- Only one instance can use the Chrome profile at a time

## Project Structure

```
LlmAgentBrowser/
├── twitter_tweet_fetcher.py  # Main demo script
├── requirements.txt          # Python dependencies
├── .env.example             # Template for API keys
├── .env                     # Your API keys (not in git)
└── README.md                # This file
```

## References

- [browser-use Documentation](https://docs.browser-use.com/)
- [browser-use GitHub](https://github.com/browser-use/browser-use)
- [Supported Models](https://docs.browser-use.com/supported-models)
