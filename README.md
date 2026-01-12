# LLM Browser Agent Demo - Twitter/X Tweet Fetcher

A demo project to evaluate different approaches for LLM-powered browser automation. Fetches tweets from your Twitter/X timeline and saves them as structured Markdown.

**Platform:** macOS (primary), Linux/Windows (partial support)

## Browser Automation Approaches

This project implements **three different approaches** for browser automation:

| Approach | Close Chrome? | Setup | Recommended |
|----------|---------------|-------|-------------|
| **Browser MCP** | **No** | Chrome Extension + MCP | **Yes** |
| browser-use | Yes | Python library | No |
| Chrome DevTools MCP | Yes | MCP Server | No |

### Why Browser MCP is Recommended

Browser MCP uses a Chrome Extension that injects into your **running browser**, so:
- No need to close Chrome windows
- Uses your existing Twitter login session
- Avoids bot detection (real browser fingerprint)
- Works alongside your normal browsing

## Quick Start (Browser MCP)

### 1. Install Browser MCP Chrome Extension

Install from [Chrome Web Store](https://chromewebstore.google.com/detail/browser-mcp-automate-your/bjfgambnhccakkhmkepdoekmckoijdlc)

### 2. Install Python Dependencies

```bash
uv sync
```

### 3. Set up API Keys

```bash
cp .env.example .env
# Edit .env and add your API keys
```

### 4. Connect the Extension (IMPORTANT!)

1. **Open Twitter/X** in a Chrome tab and make sure you're logged in
2. **Click the Browser MCP extension icon** in your Chrome toolbar
3. **Click "Connect"** in the extension popup

> The extension must be connected to the tab you want to automate. You'll see a confirmation when connected.

### 5. Run

```bash
# Recommended: Browser MCP + Claude
make bmcp-claude TWEETS=5

# Or with other models
make bmcp-gemini TWEETS=5
make bmcp-openai TWEETS=5
```

## Supported LLM Models

| Model | Provider | Used By |
|-------|----------|---------|
| Gemini 2.0 Flash | Google | Browser MCP, Chrome DevTools MCP |
| Claude Sonnet 4 | Anthropic | Browser MCP, Chrome DevTools MCP |
| GPT-4o | OpenAI | Browser MCP, Chrome DevTools MCP |
| Gemini 3 Pro | Google | browser-use |
| Claude Opus 4.5 | Anthropic | browser-use |
| GPT-5.2 | OpenAI | browser-use |

## Prerequisites

- macOS / Linux / Windows
- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) package manager
- Google Chrome with [Browser MCP Extension](https://chromewebstore.google.com/detail/browser-mcp-automate-your/bjfgambnhccakkhmkepdoekmckoijdlc)
- API keys for the LLM providers you want to use

## Installation

1. Clone this repository:
```bash
git clone <repo-url>
cd LlmAgentBrowser
```

2. Install dependencies:
```bash
uv sync
```

3. Install Browser MCP Chrome Extension from [Chrome Web Store](https://chromewebstore.google.com/detail/browser-mcp-automate-your/bjfgambnhccakkhmkepdoekmckoijdlc)

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your API keys
```

## Configuration

Edit the `.env` file with your API keys:

```env
GOOGLE_API_KEY=your-google-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
OPENAI_API_KEY=your-openai-api-key
```

### Getting API Keys

- **Google Gemini**: https://aistudio.google.com/apikey
- **Anthropic Claude**: https://console.anthropic.com/
- **OpenAI**: https://platform.openai.com/api-keys

## Usage

### Browser MCP (Recommended)

**No need to close Chrome!** Just make sure you're logged into Twitter/X.

```bash
# Using Claude (recommended)
make bmcp-claude TWEETS=5

# Using Gemini
make bmcp-gemini TWEETS=5

# Using OpenAI
make bmcp-openai TWEETS=5

# Compare all models
make bmcp-all TWEETS=5
```

### browser-use (Legacy)

**Requires closing all Chrome windows first.**

```bash
make run-gemini TWEETS=5
make run-claude TWEETS=5
make run-openai TWEETS=5
```

### Chrome DevTools MCP (Alternative)

**Requires closing all Chrome windows first.**

```bash
make mcp-gemini TWEETS=5
make mcp-claude TWEETS=5
make mcp-openai TWEETS=5
```

### All Available Commands

```bash
make help
```

### Options

| Variable | Description | Default |
|----------|-------------|---------|
| `TWEETS` | Number of tweets to fetch | 5 |
| `OUTPUT` | Output directory | `output` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | INFO |

## Output Format

Tweets are saved as structured Markdown files in the `output/` directory:

```
output/
  tweets_browsermcp_claude_20250112_143022.md
  tweets_browsermcp_gemini_20250112_143156.md
  ...
```

### Example Output:

```markdown
# Twitter/X Timeline Tweets (Browser MCP)

**Model:** Claude Sonnet 4
**Method:** Browser MCP (Chrome Extension)
**Fetched at:** 2025-01-12 14:30:22
**Execution time:** 12.45 seconds
**Tool calls:** 8

---

## Tweet 1

| Field | Value |
|-------|-------|
| **Author** | Elon Musk |
| **Handle** | @elonmusk |
| **Link** | [https://x.com/elonmusk/status/123...](https://x.com/...) |

### Content

> This is the tweet content here...

---
```

## How It Works

### Browser MCP Architecture

```
┌─────────────────┐     MCP Protocol      ┌─────────────────┐
│   LLM Client    │◄────────────────────►│  MCP Server     │
│ (Claude/Gemini) │                       │ (npx @browsermcp)│
└─────────────────┘                       └────────┬────────┘
                                                   │
                                          Chrome Extension API
                                                   │
                                          ┌────────▼────────┐
                                          │ Browser MCP     │
                                          │ Chrome Extension│
                                          └────────┬────────┘
                                                   │
                                          ┌────────▼────────┐
                                          │ Running Chrome  │
                                          │ (your tabs!)    │
                                          └─────────────────┘
```

1. **Browser MCP Extension** injects into your running Chrome
2. **MCP Server** connects to the extension via Chrome Extension API
3. **LLM** orchestrates browser actions via MCP tools
4. **Your existing login session** is preserved (Twitter, etc.)

### Available Browser MCP Tools

| Tool | Description |
|------|-------------|
| `browser_navigate` | Navigate to a URL |
| `browser_click` | Click an element |
| `browser_type` | Type text |
| `browser_press_key` | Press keyboard key |
| `browser_snapshot` | Get page content |
| `browser_screenshot` | Take screenshot |
| `browser_wait` | Wait for duration |

## Project Structure

```
LlmAgentBrowser/
├── twitter_fetcher_browsermcp.py  # Browser MCP implementation (RECOMMENDED)
├── twitter_fetcher_mcp.py         # Chrome DevTools MCP implementation
├── twitter_tweet_fetcher.py       # browser-use implementation (legacy)
├── design.md                      # Architecture design document
├── Makefile                       # Build targets
├── pyproject.toml                 # Dependencies (uv)
├── .env.example                   # API key template
├── .env                           # Your API keys (git-ignored)
└── output/                        # Generated Markdown files
```

## Troubleshooting

### "No connection to browser extension" / Extension not working

1. Install the extension from [Chrome Web Store](https://chromewebstore.google.com/detail/browser-mcp-automate-your/bjfgambnhccakkhmkepdoekmckoijdlc)
2. **Open the tab** you want to automate (e.g., Twitter/X)
3. **Click the Browser MCP extension icon** in Chrome toolbar
4. **Click "Connect"** in the popup - this is required before each session!
5. Then run your `make bmcp-*` command

### "Login required" / "Not logged in"

Make sure you're logged into Twitter/X in Chrome before running the script.

### "Rate limit exceeded"

Wait a few minutes and try again, or switch to a different LLM provider.

### browser-use / Chrome DevTools MCP: "Browser already in use"

These approaches require closing all Chrome windows first. Use **Browser MCP** instead to avoid this.

## References

- [Browser MCP](https://browsermcp.io/) - Chrome Extension + MCP Server
- [Chrome MCP Server](https://github.com/hangwin/mcp-chrome) - Alternative with more tools
- [browser-use](https://github.com/browser-use/browser-use) - Python browser automation
- [Chrome DevTools MCP](https://github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo) - Official Anthropic MCP
- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP specification
- [uv Documentation](https://docs.astral.sh/uv/) - Python package manager
