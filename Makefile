.PHONY: help install test lint format typecheck run dev docker-build docker-up docker-down clean

help:
	@echo "LLM Gateway - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  install      Install dependencies"
	@echo "  dev          Run development server"
	@echo ""
	@echo "Testing:"
	@echo "  test         Run all tests"
	@echo "  test-unit    Run unit tests only"
	@echo "  test-cov     Run tests with coverage"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint         Run ruff linter"
	@echo "  format       Format code with ruff"
	@echo "  typecheck    Run mypy type checking"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build Build Docker images"
	@echo "  docker-up    Start docker-compose stack"
	@echo "  docker-down  Stop docker-compose stack"
	@echo "  docker-logs  View docker logs"
	@echo ""
	@echo "AWS:"
	@echo "  tf-init      Initialize Terraform"
	@echo "  tf-plan      Plan Terraform changes"
	@echo "  tf-apply     Apply Terraform changes"
	@echo ""
	@echo "Utilities:"
	@echo "  clean        Clean up generated files"

install:
	pip install --upgrade pip
	pip install -r requirements.txt
	pre-commit install

test:
	pytest

test-unit:
	pytest tests/ -k "not integration"

test-cov:
	pytest --cov=src --cov-report=html --cov-report=term

lint:
	ruff check src tests

format:
	ruff format src tests

typecheck:
	mypy src

run:
	uvicorn src.gateway.main:app --reload --host 0.0.0.0 --port 8000

dev:
	docker-compose up -d redis qdrant
	uvicorn src.gateway.main:app --reload --host 0.0.0.0 --port 8000

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down -v

docker-logs:
	docker-compose logs -f

tf-init:
	cd infra && terraform init

tf-plan:
	cd infra && terraform plan

tf-apply:
	cd infra && terraform apply

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	rm -rf htmlcov .pytest_cache .mypy_cache dist build *.egg-info
	docker-compose down -v 2>/dev/null || true