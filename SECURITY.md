# Security Policy

## Intended Use

This tool is intended only for auditing VPS/proxy egress IPs that you own, rent, or are explicitly authorized to test.

## Not Supported

This project does not support:

- Bypassing CAPTCHA, Cloudflare challenge, or access control.
- Account automation.
- High-frequency probing.
- Platform restriction evasion.
- Automated browser fingerprint manipulation.

## Secrets

API keys must be provided via environment variables or local untracked config files.

Supported environment variables:

- `IPINFO_TOKEN`
- `IPREGISTRY_KEY`
- `IPDATA_KEY`
- `IPQS_KEY`
- `ABUSEIPDB_KEY`
- `MAXMIND_DB_PATH`

Do not commit generated `reports/`, raw responses, or real configs containing keys.

## Reporting Issues

If you find a security issue or an unsafe behavior path, open a private report or contact the maintainer before publishing details.
