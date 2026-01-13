.PHONY: help install run run-all run-browser-use run-gemini run-claude run-openai clean clean-logs clean-output
.PHONY: mcp-run mcp-all mcp-gemini mcp-claude mcp-openai
.PHONY: bmcp-run bmcp-all bmcp-gemini bmcp-claude bmcp-openai
.PHONY: pw-direct pw-claude pw-gemini pw-openai

# Configuration
TWEETS ?= 5
OUTPUT ?= output
LOG_LEVEL ?= INFO

# Auto-calculate scrolls: ~5 tweets per scroll, minimum 1
SCROLLS = $(shell echo $$(( ($(TWEETS) + 4) / 5 )))

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets (Browser MCP - RECOMMENDED, no need to close Chrome):"
	@awk 'BEGIN {FS = ":.*##"} /^bmcp[a-zA-Z_-]*:.*##/ {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Targets (Playwright + pycookiecheat - no need to close Chrome):"
	@awk 'BEGIN {FS = ":.*##"} /^pw-[a-zA-Z_-]*:.*##/ {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Targets (browser-use - requires closing Chrome):"
	@awk 'BEGIN {FS = ":.*##"} /^run[a-zA-Z_-]*:.*##/ {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Targets (Chrome DevTools MCP - requires closing Chrome):"
	@awk 'BEGIN {FS = ":.*##"} /^mcp[a-zA-Z_-]*:.*##/ {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Other:"
	@awk 'BEGIN {FS = ":.*##"} /^(install|clean)[a-zA-Z_-]*:.*##/ {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Variables:"
	@echo "  TWEETS=<n>       Number of tweets to fetch (default: 5)"
	@echo "  OUTPUT=<dir>     Output directory (default: output)"
	@echo "  LOG_LEVEL=<lvl>  Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)"
	@echo ""
	@echo "Examples:"
	@echo "  make bmcp-claude TWEETS=10      # Browser MCP + Claude (RECOMMENDED)"
	@echo "  make pw-direct TWEETS=10        # Playwright direct (no LLM)"
	@echo "  make pw-claude TWEETS=10        # Playwright + Claude"
	@echo "  make run-gemini TWEETS=10       # browser-use + Gemini"
	@echo "  make mcp-gemini TWEETS=10       # Chrome DevTools MCP + Gemini"

install: ## Install dependencies using uv
	uv sync

run: ## Run with default model (browser-use)
	uv run python twitter_tweet_fetcher.py --model browser-use --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL)

run-all: ## Run all models for comparison
	uv run python twitter_tweet_fetcher.py --all --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL)

run-browser-use: ## Run with Browser-Use Cloud model
	uv run python twitter_tweet_fetcher.py --model browser-use --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL)

run-gemini: ## Run with Google Gemini 3 Pro model
	uv run python twitter_tweet_fetcher.py --model gemini --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL)

run-claude: ## Run with Claude Opus 4.5 model
	uv run python twitter_tweet_fetcher.py --model claude --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL)

run-openai: ## Run with OpenAI GPT-5.2 model
	uv run python twitter_tweet_fetcher.py --model openai --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL)

clean: clean-logs clean-output ## Clean all generated files

clean-logs: ## Clean log files
	rm -rf logs/*.log

clean-output: ## Clean output files
	rm -rf output/*.md

# ============================================================================
# Chrome DevTools MCP Targets
# ============================================================================

mcp-run: mcp-gemini ## Run MCP with default model (Gemini)

mcp-all: ## Run MCP with all models for comparison
	uv run python twitter_fetcher_mcp.py --all --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL)

mcp-gemini: ## Run MCP with Gemini 2.0 Flash
	uv run python twitter_fetcher_mcp.py --model gemini --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL)

mcp-claude: ## Run MCP with Claude Sonnet 4
	uv run python twitter_fetcher_mcp.py --model claude --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL)

mcp-openai: ## Run MCP with OpenAI GPT-4o
	uv run python twitter_fetcher_mcp.py --model openai --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL)

# ============================================================================
# Browser MCP Targets (RECOMMENDED - No need to close Chrome!)
# Prerequisites:
#   1. Install Browser MCP extension from Chrome Web Store
#   2. Open Twitter/X in Chrome and login
#   3. Click Browser MCP extension icon -> Click "Connect"
#   4. Then run these commands
# ============================================================================

bmcp-run: bmcp-claude ## Run Browser MCP with default model (Claude)

bmcp-all: ## Run Browser MCP with all models for comparison
	uv run python twitter_fetcher_browsermcp.py --all --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL)

bmcp-gemini: ## Run Browser MCP with Gemini 2.0 Flash
	uv run python twitter_fetcher_browsermcp.py --model gemini --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL)

bmcp-claude: ## Run Browser MCP with Claude Sonnet 4
	uv run python twitter_fetcher_browsermcp.py --model claude --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL)

bmcp-openai: ## Run Browser MCP with OpenAI GPT-4o
	uv run python twitter_fetcher_browsermcp.py --model openai --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL)

# ============================================================================
# Playwright + pycookiecheat Targets (No need to close Chrome!)
# This approach extracts cookies from Chrome's database and uses Playwright
# to automate a separate browser instance with those cookies.
# ============================================================================

pw-direct: ## Run Playwright direct extraction (no LLM, fastest)
	uv run python twitter_fetcher_playwright.py --mode direct --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL)

pw-claude: ## Run Playwright + Claude Sonnet 4
	uv run python twitter_fetcher_playwright.py --mode llm --model claude --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL)

pw-gemini: ## Run Playwright + Gemini 2.0 Flash
	uv run python twitter_fetcher_playwright.py --mode llm --model gemini --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL)

pw-openai: ## Run Playwright + OpenAI GPT-4o
	uv run python twitter_fetcher_playwright.py --mode llm --model openai --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL)
