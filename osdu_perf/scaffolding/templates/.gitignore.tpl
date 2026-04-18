# osdu_perf scaffolded project -----------------------------------------

# Config files may contain subscription IDs, partition names, and other
# environment-specific details. Commit a redacted sample if you need to
# share; never commit real values.
config/azure_config.yaml
config/test_config.yaml

# Bundled wheels and local installs
*.whl

# Locust / pytest output
*.log
locust_report*.html
htmlcov/
.coverage
.pytest_cache/

# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
env/

# Editor / OS
.vscode/
.idea/
.DS_Store
Thumbs.db
