# Soldier Development Makefile

.PHONY: install install-dev test lint format typecheck all clean docker-up docker-down

# Default target
all: lint typecheck test

# Install production dependencies
install:
	uv sync

# Install dev dependencies
install-dev:
	uv sync --dev

# Run all tests
test:
	uv run pytest

# Run tests with coverage
test-cov:
	uv run pytest --cov=soldier --cov-report=term-missing --cov-report=html

# Run specific test file
test-file:
	uv run pytest $(FILE) -v

# Lint with ruff
lint:
	uv run ruff check soldier/ tests/

# Fix lint issues
lint-fix:
	uv run ruff check soldier/ tests/ --fix

# Format with ruff
format:
	uv run ruff format soldier/ tests/

# Check formatting without changes
format-check:
	uv run ruff format soldier/ tests/ --check

# Type check with mypy
typecheck:
	uv run mypy soldier/

# Clean build artifacts
clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Start local development stack
docker-up:
	docker-compose up -d

# Stop local development stack
docker-down:
	docker-compose down

# Rebuild and start containers
docker-rebuild:
	docker-compose up -d --build

# View logs
docker-logs:
	docker-compose logs -f

# Run the application locally
run:
	uv run python -m soldier.api

# Generate test coverage report
coverage:
	uv run pytest --cov=soldier --cov-report=html
	@echo "Coverage report: htmlcov/index.html"
