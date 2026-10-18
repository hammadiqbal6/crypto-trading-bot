.PHONY: help install install-dev lint typecheck test test-e2e dashboard validate download-data export-config pre-commit docker-up docker-down freqtrade-lookahead freqtrade-recursive backtest

PYTHON ?= python3
PIP ?= pip

help:
	@echo "Targets: install install-dev lint typecheck test test-e2e dashboard validate download-data export-config docker-up backtest"

install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev,llm-groq]"
	pre-commit install || true
	$(PYTHON) -m playwright install chromium || true

lint:
	ruff check src tests user_data/strategies
	ruff format --check src tests user_data/strategies

format:
	ruff check --fix src tests user_data/strategies
	ruff format src tests user_data/strategies

typecheck:
	mypy src/crypto_bot

test:
	pytest tests/unit tests/integration -q

test-e2e:
	pytest tests/e2e -q --cov-fail-under=0

dashboard:
	crypto-bot dashboard

validate:
	crypto-bot validate

download-data:
	crypto-bot download-data

export-config:
	crypto-bot export-freqtrade-config

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

# Requires freqtrade installed and config exported
freqtrade-lookahead:
	freqtrade lookahead-analysis -c config/freqtrade/config.json --strategy VolatilityMomentumStrategy

freqtrade-recursive:
	freqtrade recursive-analysis -c config/freqtrade/config.json --strategy VolatilityMomentumStrategy

backtest:
	freqtrade backtesting -c config/freqtrade/config.json --strategy VolatilityMomentumStrategy
