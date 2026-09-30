SHELL := /bin/bash
PY    := python3
PORT  ?= 8099
SRC   ?= /Users/kulma/Downloads

.PHONY: help data check run demo-ready deck sample clean verify

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

data: ## Rebuild artifacts/aggregate.json + baseline + backtest from the source parquet
	$(PY) -m pipeline.run --src "$(SRC)" --out artifacts

check: ## Run every gate: pipeline invariants, contract, models, privacy harness
	$(PY) -m pytest tests -q

run: ## Serve the demo locally
	@echo "demo → http://127.0.0.1:$(PORT)/app/"
	$(PY) -m http.server $(PORT) --directory .

demo-ready: ## Headless check that every preset renders real, non-empty data
	node tools/demo_ready.mjs --base http://127.0.0.1:$(PORT)

deck: ## Rebuild the slide deck PDF from docs/deck/SLIDES.md
	$(PY) tools/make_deck.py

sample: ## Regenerate the k-anonymised sample in data/samples/ (never the raw data)
	$(PY) -m pipeline.sample --out data/samples

verify: ## Recompute every number claimed in the deck and the docs
	$(PY) tools/verify_claims.py

clean:
	rm -rf artifacts/*.json artifacts/*.bin .pytest_cache **/__pycache__
