# LLM Browser Agent Demo - Twitter/X Tweet Fetcher

A demo project using [agent-browser](https://github.com/vercel-labs/agent-browser) from Vercel Labs for LLM-powered browser automation. Fetches tweets from your Twitter/X timeline and saves them as structured Markdown.

**Platform:** macOS (primary), Linux/Windows (partial support)

## Features

- **Ref-based element selection** (@e1, @e2) - optimal for LLM tool calling
- **Session isolation** - run parallel browser sessions
- **Headless or headed mode** - debug with visible browser window
- **Multi-model support** - Claude, Gemini, or OpenAI

## Quick Start

### 1. Install agent-browser

```bash
npm install -g agent-browser
agent-browser install  # Downloads Chromium (~200MB)
```

### 2. Install Python Dependencies

```bash
uv sync
```

### 3. Set up API Keys

```bash
cp .env.example .env
# Edit .env and add your API keys
```

### 4. Run

```bash
# Run with Claude (default)
make claude TWEETS=5

# Or with other models
make gemini TWEETS=5
make openai TWEETS=5

# Run with visible browser (for debugging)
make headed TWEETS=5
```

## Supported LLM Models

| Model | Provider | Command |
|-------|----------|---------|
| Claude Sonnet 4 | Anthropic | `make claude` |
| Gemini 2.0 Flash | Google | `make gemini` |
| GPT-4o | OpenAI | `make openai` |

## Prerequisites

- macOS / Linux / Windows
- Python >= 3.11
- Node.js (for agent-browser)
- [uv](https://docs.astral.sh/uv/) package manager
- API keys for the LLM providers you want to use

## Installation

1. Clone this repository:
```bash
git clone <repo-url>
cd LlmAgentBrowser
```

2. Install agent-browser:
```bash
make install-browser
# Or manually:
npm install -g agent-browser
agent-browser install
```

3. Install Python dependencies:
```bash
make install
# Or: uv sync
```

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

### Basic Commands

```bash
# Run with Claude (default)
make run

# Run with specific model
make claude TWEETS=5
make gemini TWEETS=5
make openai TWEETS=5

# Compare all models
make run-all TWEETS=5
```

### Debug Mode (Visible Browser)

```bash
# Run with visible browser window
make headed TWEETS=5
make headed-gemini TWEETS=5
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
  tweets_agentbrowser_claude_20250112_143022.md
  tweets_agentbrowser_gemini_20250112_143156.md
  ...
```

### Example Output:

```markdown
# Twitter/X Timeline Tweets (agent-browser)

**Model:** Claude Sonnet 4
**Method:** agent-browser (Playwright/Chromium)
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

### Architecture

```
┌─────────────────┐                       ┌─────────────────┐
│   LLM Client    │───subprocess/CLI────►│ agent-browser   │
│ (Claude/Gemini) │                       │  (Rust CLI)     │
└─────────────────┘                       └────────┬────────┘
                                                   │
                                          ┌────────▼────────┐
                                          │ Node.js Daemon  │
                                          │ (BrowserManager)│
                                          └────────┬────────┘
                                                   │
                                          ┌────────▼────────┐
                                          │   Playwright    │
                                          │   (Chromium)    │
                                          └─────────────────┘
```

1. **Python wrapper** calls agent-browser CLI commands via subprocess
2. **Rust CLI** communicates with persistent Node.js daemon
3. **Daemon** manages Playwright browser instance
4. **Ref-based selection** (@e1, @e2) from accessibility snapshots for LLM-optimal interaction

### Available Tools

| Tool | Description |
|------|-------------|
| `browser_open` | Navigate to a URL |
| `browser_click` | Click element by ref (@e1) or selector |
| `browser_type` | Type text into element |
| `browser_fill` | Fill input (clears first) |
| `browser_snapshot` | Get accessibility tree with element refs |
| `browser_scroll` | Scroll page up/down |
| `browser_press` | Press keyboard key |
| `browser_wait` | Wait for element or duration |
| `browser_evaluate` | Execute JavaScript |
| `browser_screenshot` | Take screenshot |
| `browser_hover` | Hover over element |
| `browser_get_text` | Get text content |

## Project Structure

```
LlmAgentBrowser/
├── twitter_fetcher_agentbrowser.py   # Main implementation
├── agent_browser_client.py           # Python wrapper for agent-browser CLI
├── Makefile                          # Build targets
├── pyproject.toml                    # Dependencies (uv)
├── .env.example                      # API key template
├── .env                              # Your API keys (git-ignored)
└── output/                           # Generated Markdown files
```

## Troubleshooting

### "agent-browser is not installed"

Install agent-browser and Chromium:
```bash
make install-browser
# Or manually:
npm install -g agent-browser
agent-browser install
```

### Twitter login required

agent-browser uses a fresh Chromium browser without your existing sessions. Use `--headed` mode to manually login:
```bash
make headed
```

### "Rate limit exceeded"

Wait a few minutes and try again, or switch to a different LLM provider.

### Command timeout

Increase the timeout by setting `LOG_LEVEL=DEBUG` to see what's happening:
```bash
make claude LOG_LEVEL=DEBUG
```

## References

- [agent-browser](https://github.com/vercel-labs/agent-browser) - Vercel Labs headless browser for AI agents
- [uv Documentation](https://docs.astral.sh/uv/) - Python package manager
