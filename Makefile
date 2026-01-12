.PHONY: help install run run-all gemini claude openai headed headed-gemini clean clean-logs clean-output chrome chrome-gemini chrome-openai

# Configuration
TWEETS ?= 5
OUTPUT ?= output
LOG_LEVEL ?= INFO

# Auto-calculate scrolls: ~5 tweets per scroll, minimum 1
SCROLLS = $(shell echo $$(( ($(TWEETS) + 4) / 5 )))

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Run with Chrome Profile (uses your existing Twitter login):"
	@awk 'BEGIN {FS = ":.*##"} /^chrome[a-zA-Z_-]*:.*##/ {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Run with Fresh Browser (requires Twitter login):"
	@awk 'BEGIN {FS = ":.*##"} /^(run|gemini|claude|openai|headed)[a-zA-Z_-]*:.*##/ {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Setup & Utility:"
	@awk 'BEGIN {FS = ":.*##"} /^(install|clean)[a-zA-Z_-]*:.*##/ {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Variables:"
	@echo "  TWEETS=<n>       Number of tweets to fetch (default: 5)"
	@echo "  OUTPUT=<dir>     Output directory (default: output)"
	@echo "  LOG_LEVEL=<lvl>  Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)"
	@echo ""
	@echo "Examples:"
	@echo "  make chrome TWEETS=10        # Use Chrome profile with Claude (RECOMMENDED)"
	@echo "  make chrome-gemini TWEETS=10 # Use Chrome profile with Gemini"
	@echo "  make claude TWEETS=10        # Fresh browser with Claude"
	@echo "  make headed                  # Fresh browser with visible window"

install: ## Install all dependencies (Python + agent-browser)
	uv sync
	npm install -g agent-browser
	agent-browser install

# ============================================================================
# Chrome Profile Targets (RECOMMENDED - uses your existing Twitter login!)
# ============================================================================

chrome: ## Run with Chrome profile + Claude (uses existing logins)
	uv run python twitter_fetcher_agentbrowser.py --model claude --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL) --use-chrome-profile

chrome-gemini: ## Run with Chrome profile + Gemini
	uv run python twitter_fetcher_agentbrowser.py --model gemini --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL) --use-chrome-profile

chrome-openai: ## Run with Chrome profile + OpenAI
	uv run python twitter_fetcher_agentbrowser.py --model openai --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL) --use-chrome-profile

# ============================================================================
# Fresh Browser Targets (requires Twitter login)
# ============================================================================

run: claude ## Run with default model (Claude)

run-all: ## Run all models for comparison
	uv run python twitter_fetcher_agentbrowser.py --all --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL)

gemini: ## Run with Gemini 2.0 Flash
	uv run python twitter_fetcher_agentbrowser.py --model gemini --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL)

claude: ## Run with Claude Sonnet 4
	uv run python twitter_fetcher_agentbrowser.py --model claude --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL)

openai: ## Run with OpenAI GPT-4o
	uv run python twitter_fetcher_agentbrowser.py --model openai --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL)

headed: ## Run with visible browser window (Claude)
	uv run python twitter_fetcher_agentbrowser.py --model claude --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL) --headed

headed-gemini: ## Run with visible browser window (Gemini)
	uv run python twitter_fetcher_agentbrowser.py --model gemini --tweets $(TWEETS) --scrolls $(SCROLLS) --output $(OUTPUT) --log-level $(LOG_LEVEL) --headed

# ============================================================================
# Cleanup
# ============================================================================

clean: clean-logs clean-output ## Clean all generated files

clean-logs: ## Clean log files
	rm -rf logs/*.log

clean-output: ## Clean output files
	rm -rf output/*.md
