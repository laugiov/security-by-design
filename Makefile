# SkyLink - Makefile
# Usage: make help

.PHONY: help build up down logs logs-gateway test clean rebuild status health

# Variables
COMPOSE = docker compose

# Default target
.DEFAULT_GOAL := help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

build: ## Build all Docker images
	$(COMPOSE) build

up: ## Start all services in background
	$(COMPOSE) up -d

down: ## Stop all services
	$(COMPOSE) down

logs: ## Follow logs for all services
	$(COMPOSE) logs -f

logs-gateway: ## Follow logs for gateway only
	$(COMPOSE) logs -f gateway

logs-telemetry: ## Follow logs for telemetry only
	$(COMPOSE) logs -f telemetry

logs-weather: ## Follow logs for weather only
	$(COMPOSE) logs -f weather

logs-contacts: ## Follow logs for contacts only
	$(COMPOSE) logs -f contacts

test: ## Run tests in gateway container
	$(COMPOSE) run --rm gateway pytest tests/

clean: ## Remove containers, volumes, and local images
	$(COMPOSE) down -v --rmi local --remove-orphans

rebuild: down build up ## Rebuild and restart all services

status: ## Show status of all services
	$(COMPOSE) ps

health: ## Check health of all services
	@echo "=== SkyLink Health Check ==="
	@echo -n "Gateway:    " && curl -sf http://localhost:8000/health 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','ERROR'))" || echo "DOWN"
	@echo -n "Telemetry:  " && $(COMPOSE) exec -T telemetry python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8001/health').read().decode())" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','ERROR'))" || echo "DOWN"
	@echo -n "Weather:    " && $(COMPOSE) exec -T weather python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8002/health').read().decode())" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','ERROR'))" || echo "DOWN"
	@echo -n "Contacts:   " && $(COMPOSE) exec -T contacts python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8003/health').read().decode())" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','ERROR'))" || echo "DOWN"
	@echo -n "PostgreSQL: " && $(COMPOSE) exec -T db pg_isready -U skylink -q && echo "UP" || echo "DOWN"

shell-gateway: ## Open shell in gateway container
	$(COMPOSE) exec gateway /bin/bash

shell-db: ## Open psql in database container
	$(COMPOSE) exec db psql -U skylink -d skylink
