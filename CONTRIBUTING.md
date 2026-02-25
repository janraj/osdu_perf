# Contributing

Thanks for contributing to `osdu_perf`.

## Development Setup

1. Create and activate a virtual environment.
2. Install project and dev dependencies:

```bash
pip install -e .
pip install -r requirements.txt
pip install pytest pytest-cov build twine
```

## Coding Guidelines

- Keep changes focused and minimal.
- Follow existing project structure and naming.
- Do not commit secrets or credentials.
- Update documentation when behavior changes.

## Testing

Run unit tests before opening a PR:

```bash
pytest tests/unit -q
```

## Pull Requests

- Use clear commit messages.
- Reference related issues when applicable.
- Ensure PR gate checks are green before requesting review.
- Keep PRs small enough for efficient review.

## Release Behavior

Publishing is automated on push to `main`:
- Commit message containing `major` triggers major bump.
- Commit message containing `minor` triggers minor bump.
- Otherwise patch bump is applied.

## Code of Conduct

By participating, you agree to collaborate respectfully and professionally.
