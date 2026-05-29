# ARAON Core

Shared runtime library for ARAON desktop tools.

This repository is used by:

- ARAON Setup

## Scope

Keep technical/common infrastructure here:

- configuration and local settings migration
- keyring-based LMS credential storage
- Google Sheets authentication helpers
- Playwright browser/session creation and cleanup
- LMS login/search/detail helpers
- logging
- GitHub Release updater
- shared sheet/cache utilities

Business-specific workflow code should stay in the app repositories.

## Install

```bat
python -m pip install git+https://github.com/swseokx/araon-core.git@main
python -m playwright install chromium
```
