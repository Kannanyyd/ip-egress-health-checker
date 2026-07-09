## Summary

- 

## Verification

- [ ] `python -m py_compile main.py ip_audit.py ip_health_checker/*.py ip_health_checker/collectors/*.py ip_health_checker/checks/*.py`
- [ ] `python tools/privacy_scan.py`
- [ ] `python main.py --proxies proxies.example.txt --dry-run`
- [ ] Quick report run, if behavior changed

## Safety

- [ ] No CAPTCHA/challenge bypass logic
- [ ] No real IPs, emails, secrets, local paths, or generated reports committed
- [ ] Scoring/report changes documented
