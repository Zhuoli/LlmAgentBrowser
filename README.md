# LLM Browser Agent Demo - Twitter/X Tweet Fetcher

A demo project to evaluate different approaches for LLM-powered browser automation. Fetches tweets from your Twitter/X timeline and saves them as structured Markdown.

**Platform:** macOS (primary), Linux/Windows (partial support)

## Browser Automation Approaches

This project implements **four different approaches** for browser automation:

| Approach | Close Chrome? | Setup | Control | Recommended |
|----------|---------------|-------|---------|-------------|
| **Playwright + pycookiecheat** | **No** | Python packages only | Direct Python | **Yes (Default)** |
| Browser MCP | No | Chrome Extension + MCP | MCP tools | Alternative |
| browser-use | Yes | Python library | Via library | Legacy |
| Chrome DevTools MCP | Yes | MCP Server | MCP tools | Legacy |

### Why Playwright + pycookiecheat is Recommended

A pure Python approach that extracts cookies from Chrome's database:
- **No need to close Chrome** - cookies extracted from SQLite database
- **No browser extension required** - just Python packages
- **Fast** - direct extraction mode completes in ~7 seconds
- **Full Playwright API** - direct Python control without MCP overhead
- **Dual mode support** - direct extraction (no LLM) or LLM-guided
- Uses your existing Twitter login session via cookies

### Browser MCP Alternative

Browser MCP uses a Chrome Extension that injects into your running browser:
- No need to close Chrome windows
- Requires installing Chrome extension and clicking "Connect" each session
- Uses MCP protocol for tool orchestration

## Quick Start (Playwright + pycookiecheat)

### 1. Install Python Dependencies

```bash
uv sync
uv run playwright install chromium
```

### 2. Login to Twitter/X in Chrome

Make sure you're logged into Twitter/X in your Chrome browser.

### 3. Run

```bash
# Direct extraction (fastest, no LLM needed)
make pw-direct TWEETS=5

# Or with LLM guidance
make pw-claude TWEETS=5
make pw-gemini TWEETS=5
make pw-openai TWEETS=5
```

> **Note:** On first run, macOS will ask for Keychain access to decrypt Chrome cookies. Click "Allow" or "Always Allow".

## Supported LLM Models

| Model | Provider | Used By |
|-------|----------|---------|
| Gemini 2.0 Flash | Google | Playwright, Browser MCP, Chrome DevTools MCP |
| Claude Sonnet 4 | Anthropic | Playwright, Browser MCP, Chrome DevTools MCP |
| GPT-4o | OpenAI | Playwright, Browser MCP, Chrome DevTools MCP |
| Gemini 3 Pro | Google | browser-use |
| Claude Opus 4.5 | Anthropic | browser-use |
| GPT-5.2 | OpenAI | browser-use |

## Prerequisites

- macOS / Linux / Windows
- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) package manager
- Google Chrome (logged into Twitter/X)
- API keys for the LLM providers (only needed for LLM-guided modes)

## Installation

1. Clone this repository:
```bash
git clone <repo-url>
cd LlmAgentBrowser
```

2. Install dependencies:
```bash
uv sync
uv run playwright install chromium
```

3. Set up environment variables (optional, only for LLM modes):
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

### Playwright + pycookiecheat (Recommended)

**No need to close Chrome!** Cookies are extracted from Chrome's database.

```bash
# Direct extraction (no LLM, fastest ~7 seconds)
make pw-direct TWEETS=5

# LLM-guided extraction
make pw-claude TWEETS=5
make pw-gemini TWEETS=5
make pw-openai TWEETS=5
```

### Browser MCP (Alternative)

**No need to close Chrome!** Requires Chrome extension.

```bash
# First: Install extension and click "Connect"
make bmcp-claude TWEETS=5
make bmcp-gemini TWEETS=5
make bmcp-openai TWEETS=5
```

### browser-use (Legacy)

**Requires closing all Chrome windows first.**

```bash
make run-gemini TWEETS=5
make run-claude TWEETS=5
make run-openai TWEETS=5
```

### Chrome DevTools MCP (Legacy)

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
  tweets_playwright_direct_20250112_143022.md
  tweets_playwright_claude_20250112_143156.md
  ...
```

### Example Output:

```markdown
# Twitter/X Timeline Tweets (Playwright + pycookiecheat)

**Model:** Direct (No LLM)
**Method:** pycookiecheat + Playwright
**Fetched at:** 2025-01-12 14:30:22
**Execution time:** 7.20 seconds

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

### Playwright + pycookiecheat Architecture

```
┌─────────────────┐
│  Your Chrome    │
│  (logged in)    │
└────────┬────────┘
         │ Cookies stored in SQLite
         ▼
┌─────────────────┐
│  pycookiecheat  │  ← Extracts & decrypts cookies
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│   Playwright    │────►│ New Chromium    │
│   (Python)      │     │ with cookies    │
└─────────────────┘     └─────────────────┘
```

1. **pycookiecheat** reads Chrome's cookie database and decrypts cookies using macOS Keychain
2. **Playwright** launches a new Chromium instance and injects the cookies
3. **Direct mode**: Playwright navigates and extracts tweets using selectors
4. **LLM mode**: LLM orchestrates Playwright tools for navigation and extraction

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
├── twitter_fetcher_playwright.py  # Playwright + pycookiecheat (RECOMMENDED)
├── twitter_fetcher_browsermcp.py  # Browser MCP implementation
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

### Keychain access prompt (macOS)

On first run, macOS will ask: "python wants to use your confidential information stored in Chrome Safe Storage in your keychain"

- Click **"Allow"** for one-time access, or **"Always Allow"** to remember
- This is required because Chrome encrypts cookies and pycookiecheat needs the decryption key

### "No cookies found" error

Make sure you're logged into Twitter/X in Chrome (not Safari or another browser).

### "No connection to browser extension" / Extension not working (Browser MCP)

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
- [Playwright](https://playwright.dev/python/) - Modern browser automation
- [pycookiecheat](https://github.com/n8henrie/pycookiecheat) - Extract Chrome cookies
- [Chrome MCP Server](https://github.com/hangwin/mcp-chrome) - Alternative with more tools
- [browser-use](https://github.com/browser-use/browser-use) - Python browser automation
- [Chrome DevTools MCP](https://github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo) - Official Anthropic MCP
- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP specification
- [uv Documentation](https://docs.astral.sh/uv/) - Python package manager
