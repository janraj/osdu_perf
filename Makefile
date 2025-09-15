.PHONY: test test-unit test-integration test-cov clean lint format

# Run all tests
test:
	pytest

# Run only unit tests
test-unit:
	pytest -m unit

# Run only integration tests  
test-integration:
	pytest -m integration

# Run tests with coverage report
test-cov:
	pytest --cov=osdu_perf --cov-report=html --cov-report=term

# Clean up generated files
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage

# Run linting
lint:
	flake8 osdu_perf tests

# Format code
format:
	black osdu_perf tests
