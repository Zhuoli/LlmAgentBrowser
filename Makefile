.PHONY: help install run run-all gemini claude openai headed headed-gemini clean clean-logs clean-output

# Configuration
TWEETS ?= 5
OUTPUT ?= output
LOG_LEVEL ?= INFO

# Auto-calculate scrolls: ~5 tweets per scroll, minimum 1
SCROLLS = $(shell echo $$(( ($(TWEETS) + 4) / 5 )))

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "agent-browser Targets (Vercel Labs - Playwright/Chromium):"
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ && !/^(install|clean)/ {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
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
	@echo "  make claude TWEETS=10       # Run with Claude Sonnet 4"
	@echo "  make gemini TWEETS=10       # Run with Gemini 2.0 Flash"
	@echo "  make headed                 # Run with visible browser window"

install: ## Install dependencies using uv
	uv sync

install-browser: ## Install agent-browser CLI and Chromium
	npm install -g agent-browser
	agent-browser install

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

clean: clean-logs clean-output ## Clean all generated files

clean-logs: ## Clean log files
	rm -rf logs/*.log

clean-output: ## Clean output files
	rm -rf output/*.md
