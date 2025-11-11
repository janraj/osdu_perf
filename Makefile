.PHONY: test test-unit test-cov clean clean-win lint format install help

# Run all tests
test:
	pytest tests/unit/

# Run only unit tests (same as test since we only have unit tests)
test-unit:
	pytest tests/unit/

# Run tests with coverage report
test-cov:
	pytest tests/unit/ --cov=osdu_perf --cov-report=html --cov-report=term-missing

# Install package in development mode
install:
	pip install -e .

# Clean up generated files (Unix/Linux/Mac)
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage osdu_perf.egg-info 2>/dev/null || true

# Clean up generated files (Windows - use: make clean-win)
clean-win:
	@echo "Cleaning up generated files..."
	@for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d" 2>nul
	@del /s /q *.pyc 2>nul || true
	@if exist .pytest_cache rmdir /s /q .pytest_cache 2>nul
	@if exist htmlcov rmdir /s /q htmlcov 2>nul
	@if exist .coverage del .coverage 2>nul
	@if exist osdu_perf.egg-info rmdir /s /q osdu_perf.egg-info 2>nul
	@echo "Cleanup complete."

# Run linting
lint:
	flake8 osdu_perf tests

# Format code
format:
	black osdu_perf tests

# Show help
help:
	@echo "Available targets:"
	@echo "  test        - Run all unit tests"
	@echo "  test-unit   - Run unit tests (same as test)"
	@echo "  test-cov    - Run tests with coverage report"
	@echo "  install     - Install package in development mode"
	@echo "  clean       - Clean up generated files (Unix/Linux/Mac)"
	@echo "  clean-win   - Clean up generated files (Windows)"
	@echo "  lint        - Run code linting"
	@echo "  format      - Format code with black"
	@echo "  help        - Show this help message"
