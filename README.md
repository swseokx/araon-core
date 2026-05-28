# ARAON Core

Shared runtime library for ARAON desktop tools.

This repository is used by:

- ARAON Setup
- ARAON Orientation

## Scope

Keep technical/common infrastructure here:

- configuration and local settings migration
- keyring-based LMS credential storage
- Google Sheets authentication helpers
- Selenium/ChromeDriver creation and cleanup
- LMS login helpers
- logging
- GitHub Release updater
- shared sheet/cache utilities

Business-specific workflow code should stay in the app repositories.

## Install

```bat
python -m pip install git+https://github.com/swseokx/araon-core.git@v1.0.0
```

