# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## Reporting a Vulnerability

**DO NOT** report security vulnerabilities through public GitHub issues.

Report vulnerabilities via email to: **security@goondocks.co**

Include in your report:

- Type of vulnerability
- Affected source file(s) and location (tag/branch/commit or URL)
- Steps to reproduce
- Proof-of-concept or exploit code (if possible)
- Impact assessment

### Response Timeline

| Stage | Timeframe |
|-------|-----------|
| Initial acknowledgment | Within 48 hours |
| Status updates | At least every 7 days |
| Coordinated disclosure | Within 90 days |

### What to Expect

1. Acknowledgment within 48 hours
2. Assessment of vulnerability and impact
3. Plan for remediation
4. Regular progress updates
5. Credit for discovery (if desired) upon disclosure

## Security Best Practices

- **Never commit secrets** — use environment variables (`GITHUB_TOKEN`, `ANTHROPIC_API_KEY`)
- **Review AI-generated output** before applying changes to your codebase
- **Protect `.oak/` directory** — it contains project configuration
- **Use minimal token scopes** and rotate API tokens regularly

## Security Updates

Security patches are released as patch versions and announced via:

- [GitHub Security Advisories](https://github.com/goondocks-co/open-agent-kit/security/advisories)
- [GitHub Releases](https://github.com/goondocks-co/open-agent-kit/releases)

## Contact

- **Vulnerability reports**: security@goondocks.co (email only)
- **General security questions**: [GitHub Discussions](https://github.com/goondocks-co/open-agent-kit/discussions)
