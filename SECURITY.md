# Security Policy

## Supported Versions

We actively support the following versions of open-agent-kit with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 0.3.x   | :white_check_mark: |
| < 0.3   | :x:                |

## Reporting a Vulnerability

We take the security of open-agent-kit seriously. If you discover a security vulnerability, please follow these guidelines:

### Reporting Process

**DO NOT** report security vulnerabilities through public GitHub issues.

Instead, please report security vulnerabilities via email to:

**opensource@example.com**

Include the following information in your report:

* Type of vulnerability
* Full paths of source file(s) related to the manifestation of the vulnerability
* The location of the affected source code (tag/branch/commit or direct URL)
* Step-by-step instructions to reproduce the issue
* Proof-of-concept or exploit code (if possible)
* Impact of the vulnerability, including how an attacker might exploit it

### Response Timeline

* **Initial Response**: We will acknowledge receipt of your vulnerability report within 48 hours
* **Status Updates**: You can expect regular updates on the status at least every 7 days
* **Disclosure Timeline**: We aim to disclose vulnerabilities within 90 days of the initial report, coordinating with you on the disclosure date

### What to Expect

After submitting a vulnerability report, you can expect:

1. Acknowledgment of your report within 48 hours
2. An assessment of the vulnerability and its impact
3. A plan for addressing the vulnerability
4. Regular updates on our progress
5. Credit for the discovery (if desired) when the vulnerability is publicly disclosed

## Security Considerations

When using open-agent-kit, please observe these security best practices:

### Credentials and Secrets

* **Never store API keys or secrets in configuration files**
* Use environment variables for sensitive credentials (e.g., `GITHUB_TOKEN`, `ANTHROPIC_API_KEY`)
* Ensure `.gitignore` excludes any files containing secrets
* Review generated files before committing to avoid accidental exposure of sensitive data

### CLI Tool Security

* Run `oak` commands with the minimum necessary privileges
* Be cautious when executing agent-generated code or commands
* Review agent outputs before applying changes to your codebase
* Keep your Python environment and dependencies up to date

### Configuration Files

* Protect write access to `.oak/` directory and configuration files
* Review agent manifests and feature definitions for unexpected behavior
* Use version control to track changes to configuration files

### API Access

* Use read-only tokens when possible for issue tracking integrations
* Rotate API tokens regularly
* Limit token scope to only the required permissions

## Disclosure Policy

When we receive a security vulnerability report, we will:

1. Confirm the issue and determine affected versions
2. Audit code to find similar potential issues
3. Prepare fixes for all supported versions
4. Release patches as quickly as possible
5. Credit the reporter (unless anonymity is requested)
6. Publish a security advisory with details and mitigation steps

## Security Updates

Security updates will be released as patch versions (e.g., 0.3.1) and announced via:

* GitHub Security Advisories
* Release notes in CHANGELOG.md
* GitHub releases page

We recommend keeping open-agent-kit updated to the latest patch version of your major release.

## Contact

For security-related questions that are not vulnerability reports, you can:

* Open a discussion on GitHub Discussions
* Contact the maintainers at opensource@example.com

For vulnerability reports, always use the email reporting process described above.
