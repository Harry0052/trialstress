# Security

TrialStress is a local calculator for synthetic design assumptions. It does not authenticate users, store personal data, or call a service.

## Reporting a vulnerability

Use GitHub private vulnerability reporting on [Harry0052/trialstress](https://github.com/Harry0052/trialstress/security). Do not open a public issue for a security report, and do not include secrets, credentials, or personal data in the report.

## What the tool accepts

Scenario files are untrusted input. The parser rejects oversized files, nonfinite numbers, and values outside the job budget before simulation. Reports are written only as `report.json`, `report.html`, and `report.txt` inside the directory named by `-o`. The HTML report escapes scenario text.

There is no network access at runtime and no credential file. Do not put secrets in a scenario, a fixture, or an issue.
