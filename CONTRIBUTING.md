# Contributing

Thanks for helping maintain this project.

## Development Principles

- Keep checks low-frequency and respectful.
- Prefer public APIs and DNS queries over scraping.
- Treat access challenges as a result, not as something to bypass.
- Keep generated reports and raw outputs out of git.
- Make scoring changes explainable and documented.

## Local Verification

```bash
PYTHONPYCACHEPREFIX=/tmp/ip_health_pycache python3 -m py_compile main.py ip_audit.py ip_health_checker/*.py ip_health_checker/collectors/*.py ip_health_checker/checks/*.py
python3 main.py --ips ips.example.txt --dry-run
python3 main.py --ips ips.example.txt --quick --format md,csv,json --output /tmp/ip_health_reports
```

## Pull Request Checklist

- [ ] No secrets or generated reports committed.
- [ ] New source failures do not abort the whole run.
- [ ] Safety boundaries are preserved.
- [ ] `README.md` or `docs/` updated when behavior changes.
- [ ] `CHANGELOG.md` updated for user-visible changes.
