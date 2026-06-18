# Security Policy

## Reporting a Vulnerability

If you discover a security issue in ContextPoison — or have concerns about the
benchmark data or findings in this repository — please report it privately
rather than opening a public issue.

**Contact:** dempster.connor10@yahoo.com

Please include:

- a description of the issue and its impact,
- steps to reproduce, and
- any relevant logs or proof-of-concept (do **not** include live API keys).

You can expect an acknowledgement within **7 days**. I aim to provide a
resolution or remediation plan within **30 days**, and will coordinate a
disclosure timeline with you before any public write-up.

## Scope

This project benchmarks third-party AI models using their official public APIs.
Vulnerabilities in those upstream models should be reported to the respective
provider under their own responsible-disclosure process. Findings about model
behaviour surfaced by this tool are disclosed to the affected provider before
publication.

## Secrets

This repository contains no credentials. API keys are read from environment
variables at runtime and must never be committed. If you believe a secret has
been committed, report it via the contact above so it can be rotated.
