# LLM Browser Agent Demo - Twitter/X Tweet Fetcher

A demo project to evaluate different LLM models using [browser-use](https://github.com/browser-use/browser-use) for autonomous web browsing. Fetches tweets from your Twitter/X timeline and saves them as structured Markdown.

**Platform:** macOS only

## Supported LLM Models

| Model | Provider | Model ID |
|-------|----------|----------|
| ChatBrowserUse | Browser-Use Cloud | Built-in |
| Gemini 2.5 Pro | Google | `gemini-2.5-pro` |
| Claude Opus 4.5 | Anthropic | `claude-opus-4-5-20251101` |
| GPT-5.2 | OpenAI | `gpt-5.2` |

## Prerequisites

- macOS
- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) package manager
- Google Chrome (with your Twitter/X account logged in)
- API keys for the LLM providers you want to test

## Installation

1. Clone this repository:
```bash
git clone <repo-url>
cd LlmAgentBrowser
```

2. Install dependencies with uv:
```bash
uv sync
```

3. Install browser-use CLI tools:
```bash
uv run browser-use install
```

4. Set up your environment variables:
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

**Important**: Close all Chrome browser windows before running.

### Test a single model:

```bash
# Using Google Gemini
uv run python twitter_tweet_fetcher.py --model gemini

# Using Claude Opus 4.5
uv run python twitter_tweet_fetcher.py --model claude

# Using OpenAI GPT-5.2
uv run python twitter_tweet_fetcher.py --model openai

# Using Browser-Use Cloud
uv run python twitter_tweet_fetcher.py --model browser-use
```

### Test all models for comparison:

```bash
uv run python twitter_tweet_fetcher.py --all
```

### Options:

```bash
uv run python twitter_tweet_fetcher.py --model gemini --tweets 10 --output my_tweets
```

| Option | Description | Default |
|--------|-------------|---------|
| `--model` | LLM model to use | Required (or use --all) |
| `--all` | Run all models for comparison | - |
| `--tweets` | Number of tweets to fetch | 5 |
| `--output` | Output directory for Markdown files | `output` |

## Output Format

Tweets are saved as structured Markdown files in the `output/` directory:

```
output/
  tweets_gemini_20250112_143022.md
  tweets_claude_20250112_143156.md
  ...
```

### Example Markdown Output:

```markdown
# Twitter/X Timeline Tweets

**Model:** Google Gemini 2.5 Pro
**Fetched at:** 2025-01-12 14:30:22
**Execution time:** 45.32 seconds

---

## Tweet 1

| Field | Value |
|-------|-------|
| **Author** | Elon Musk |
| **Handle** | @elonmusk |
| **Link** | [https://x.com/elonmusk/status/123...](https://x.com/elonmusk/status/123...) |
| **Time** | 2h |

### Content

> This is the tweet content here...

**Engagement:** 1234 likes | 567 retweets

---
```

## How It Works

1. **Browser Connection**: Connects to Chrome using your default profile (where you're logged into Twitter/X)
2. **Agent Execution**: The LLM agent navigates to Twitter/X and waits for timeline to load
3. **Tweet Extraction**: Agent extracts author, handle, content, link, and engagement metrics
4. **Markdown Export**: Results are saved as structured Markdown for easy reading

## Troubleshooting

### "Chrome profile not found"
Ensure Chrome is installed at `/Applications/Google Chrome.app`

### "Login required"
Make sure you're logged into Twitter/X in Chrome before running

### "Browser already in use"
Close all Chrome windows before running the script

## Project Structure

```
LlmAgentBrowser/
├── twitter_tweet_fetcher.py  # Main demo script
├── pyproject.toml            # Project config & dependencies (uv)
├── .env.example              # Template for API keys
├── .env                      # Your API keys (git-ignored)
├── .gitignore
├── README.md
└── output/                   # Generated Markdown files
    └── tweets_*.md
```

## References

- [browser-use Documentation](https://docs.browser-use.com/)
- [browser-use GitHub](https://github.com/browser-use/browser-use)
- [uv Documentation](https://docs.astral.sh/uv/)
