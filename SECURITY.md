# Security Policy

## Reporting a vulnerability

Please report security vulnerabilities privately through GitHub's private vulnerability reporting feature when it is available for this repository. If that channel is unavailable, contact the repository owner privately before disclosing technical details. Do not open a public issue containing an exploit, credential, client information, licensed data, or a confidential formulation.

Include the affected version or commit, reproduction steps, impact, and any suggested mitigation. Maintainers will acknowledge the report, investigate it, and coordinate disclosure after a fix is available.

## Sensitive and restricted data

Never commit:

- API keys, tokens, passwords, credentials, private keys, or `.env` files
- official bulk ECHA exports whose redistribution is restricted or unclear
- proprietary CAS datasets or other licensed reference databases
- client files, SDS documents, formulations, or confidential regulatory records
- private dataset snapshots or local databases containing restricted records

User-supplied regulatory datasets must remain in access-controlled local storage. Public tests and examples must use synthetic data or small fixtures whose redistribution is documented as permissible.

If sensitive material is committed, stop sharing the affected revision, revoke exposed credentials, notify the maintainer privately, remove the material from reachable Git history, and verify the cleaned repository before publication.

## Supported versions

Security fixes are applied to the latest version on the default branch. Older commits and unmaintained forks are not supported.
