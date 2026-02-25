# Security Policy

## Supported Versions

The latest published PyPI release and the `main` branch are actively supported.

## Reporting a Vulnerability

Please do not open public GitHub issues for security vulnerabilities.

Report vulnerabilities privately via one of the following channels:
- GitHub Security Advisories (preferred): use the repository **Security** tab and click **Report a vulnerability**.
- Email: janrajcj@microsoft.com

Include as much detail as possible:
- Affected version/commit
- Reproduction steps or proof of concept
- Impact assessment
- Any suggested mitigation

## Response Process

- We acknowledge valid reports as quickly as possible.
- We investigate, reproduce, and prioritize based on impact.
- We coordinate disclosure and release a fix.

## Secrets and Credentials

- Never commit tokens, passwords, keys, or connection strings.
- Use GitHub Actions secrets for CI/CD (`PYPI_API_TOKEN`, OSDU credentials, etc.).
- Use environment variables for local runtime credentials.
