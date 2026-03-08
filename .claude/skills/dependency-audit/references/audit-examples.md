# Dependency Audit Examples

## Good Audit Report (Excerpt)

This excerpt demonstrates a useful dependency audit — specific version data,
risk-assessed conflicts, and prioritized remediation steps.

---

### Executive Summary

Audited 4 projects across the swarm. Found 3 high-risk version conflicts
(pydantic v1/v2 split, React 17/18 mismatch, outdated `cryptography` package),
7 moderate alignment opportunities, and 12 shared dependencies already in sync.
Top priority: upgrade `cryptography` in `billing-service` from 38.0 to 42.x
(security patches).

### Version Conflict Analysis

| Package | api-gateway | user-service | billing-service | Risk | Notes |
|---------|-------------|-------------|-----------------|------|-------|
| pydantic | 2.6.1 | 2.4.0 | 1.10.14 | **High** | v1 → v2 is a breaking migration. billing-service blocked by payment provider SDK |
| cryptography | 42.0.5 | 42.0.5 | 38.0.0 | **High** | v38 is missing security patches for CVE-2024-XXXXX |
| fastapi | 0.109.0 | 0.109.0 | 0.104.1 | Medium | billing-service 5 minor versions behind, should align after pydantic upgrade |
| httpx | 0.27.0 | 0.26.0 | 0.27.0 | Low | Minor version difference, no breaking changes |

### Security Assessment

**Critical:**
- `billing-service` uses `cryptography==38.0.0`, which is 4 major versions
  behind and missing patches for known vulnerabilities. Upgrade path is
  straightforward (no API changes between 38 and 42).

**Watch:**
- `user-service` pins `PyJWT==2.6.0` while `api-gateway` uses `2.8.0`. The
  2.7.0 release included a fix for algorithm confusion attacks. Recommend
  aligning to 2.8.0.

### Standardization Recommendations

| Action | Priority | Packages | Projects Affected |
|--------|----------|----------|-------------------|
| Upgrade cryptography | Critical | cryptography 38→42 | billing-service |
| Align pydantic to v2.6 | High | pydantic 1.10→2.6 | billing-service |
| Align fastapi | Medium | fastapi 0.104→0.109 | billing-service |
| Align PyJWT | Medium | PyJWT 2.6→2.8 | user-service |

---

## Why This Audit is Good

- **Risk levels are justified** — "High" isn't arbitrary; it cites the specific
  CVE or breaking change that makes the conflict dangerous.
- **Blockers are identified** — notes that billing-service can't upgrade
  pydantic until the payment provider SDK supports v2.
- **Table format enables scanning** — a manager can look at the conflict table
  and immediately see the problem without reading paragraphs.
- **Recommendations are ordered** — critical security issues first, then
  breaking version splits, then alignment opportunities.
- **Shared dependencies noted** — the audit acknowledges what's already aligned,
  not just what's broken.

---

## Bad Audit Report (Excerpt)

---

### Dependencies

The projects use various packages. Some are on different versions. Here are
some notable ones:
- pydantic is used in multiple projects
- Some projects have older versions of things
- There might be security issues

### Recommendations

- Update everything to latest
- Use the same versions across projects
- Check for security vulnerabilities regularly

---

## Why This Audit is Bad

- **No version numbers** — "Some projects have older versions" is useless
  without saying which versions of which packages in which projects.
- **No risk assessment** — "There might be security issues" is not an audit
  finding. Either there are specific CVEs or there aren't.
- **"Update everything to latest" is dangerous** — major version bumps can
  break things. A real audit identifies which updates are safe, which need
  migration effort, and what order to do them in.
- **No prioritization** — a security vulnerability and a minor version
  difference are treated the same (not at all).
- **No project attribution** — never says which project has which problem.

---

## Risk Assessment Framework

When evaluating dependency conflicts, assess risk on these dimensions:

| Factor | High Risk | Medium Risk | Low Risk |
|--------|-----------|-------------|----------|
| **Version gap** | Major version mismatch (v1 vs v3) | Multiple minor versions (0.104 vs 0.109) | Patch versions only (1.2.3 vs 1.2.5) |
| **Security** | Known CVEs in older version | Deprecated features | No security implications |
| **API surface** | Package defines shared interfaces (serialization, auth) | Internal utility only | Dev/test dependency only |
| **Migration effort** | Breaking API changes, data migration needed | New deprecation warnings | Drop-in replacement |

High risk on any dimension warrants a recommendation. High risk on 2+
dimensions warrants a "Critical" priority.
