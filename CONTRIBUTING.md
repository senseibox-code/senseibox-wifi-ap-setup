# Contributing

Hi! Thanks for wanting to contribute to Senseibox. This software depends on the hardware, so small fixes, tests, and feedback can make a real difference.

Before opening a pull request, please take a few minutes to read these guidelines. They help keep contributions easy to review, safe to ship, and practical on the Linux systems this app runs on.

## Development Setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
senseibox-wifi-ap-mode --web-only --reload
```

Use `--web-only` for local UI and API work. Full AP mode uses Linux networking tools such as NetworkManager, `iw`, `hostapd`, and `dnsmasq`, so it should be tested on Linux hardware or a suitable Linux VM.

The app is intentionally small:

- `src/senseibox_wifi_ap_mode/app.py` exposes the web app and API routes.
- `src/senseibox_wifi_ap_mode/network.py` handles NetworkManager, Wi-Fi scanning, and interface detection.
- `src/senseibox_wifi_ap_mode/ap.py` generates AP configuration and controls `hostapd`/`dnsmasq`.
- `src/senseibox_wifi_ap_mode/service.py` coordinates boot checks, setup mode, and timeout behavior.
- `static/` contains the setup UI with no frontend build step.
- `systemd/` contains the tracked service unit.

## Local Checks

Run these before opening a PR:

```bash
python -m compileall -q src tests
pytest -q
node --check static/setup.js
bash -n install.sh
```

When changing AP mode, Wi-Fi scanning, NetworkManager handoff, or `hostapd`/`dnsmasq` behavior, also test on Linux hardware whenever possible. macOS can run the unit tests and web-only mode, but it cannot validate the real AP lifecycle.

## Hardware and Networking Notes

Please be extra careful around network ownership:

- Do not hardcode interface names such as `wlan0`; detect wireless interfaces dynamically.
- Validate AP mode support before trying to start `hostapd`.
- Make sure NetworkManager does not manage the AP interface while `hostapd` owns it.
- Do not log Wi-Fi passwords or include them in error messages.
- Pass subprocess arguments as lists instead of building shell command strings.
- Keep setup AP mode isolated; this project is not a bridged Wi-Fi extender.

If a change depends on a specific chipset, driver, distro image, or board behavior, include that context in the PR.

## Web UI Contributions

Before implementing or substantially changing the setup UI, ask for the current designs. The setup UI should stay visually aligned with the Senseibox KPI app where practical.

Small accessibility, copy, layout, and error-state fixes are very welcome. For larger interaction changes, please open an issue first so we can agree on the flow.

## Pull Request Guidelines

- Checkout a topic branch from the relevant base branch, usually `main`, and target your PR back to that branch.
- For a new feature, explain why it belongs in the product. Opening a suggestion issue first is strongly encouraged.
- For a bug fix, include a clear description of the bug, expected behavior, actual behavior, and reproduction steps. Logs or a short demo are very helpful.
- Keep changes focused. A small PR with a crisp purpose is a gift to reviewers.
- It is fine to have multiple small commits while you work. GitHub can squash them before merge.
- Update `PRD.spec` when requirements or expected behavior change.
- Update README or operational docs when install, service, API, or debugging behavior changes.
- Add or update tests for behavior changes.

## Privacy and Safety

Never commit personal information or secrets. This includes local usernames, real names, personal email addresses, private IPs, passwords, SSH key names, local machine names, and local filesystem paths.

Before committing, scan for private identifiers such as local home-directory paths, private network addresses, personal email domains, SSH key names, local machine names, and real user names. If the scan finds a real private value, remove it before committing. Use generic product paths such as `/opt/senseibox/senseibox-wifi-ap-mode` in docs and code.

## Git Commit Message Convention

Use conventional commit-style messages so changelogs and release notes can be generated automatically.

Format:

```text
<type>(<scope>): <subject>

<body>

<footer>
```

The scope, body, and footer are optional. The header is required.

Recommended types:

- `feat`: user-facing feature
- `fix`: bug fix
- `perf`: performance improvement
- `docs`: documentation-only change
- `test`: test-only change
- `refactor`: code change with no intended behavior change
- `style`: formatting or visual styling with no behavior change
- `build`: packaging or build-system change
- `ci`: CI configuration change
- `chore`: maintenance task
- `revert`: revert a previous commit

Examples:

```text
feat(ap): generate hostapd config at runtime
```

```text
fix(network): restore NetworkManager after AP startup failure
```

```text
docs: add board testing checklist
```

Subjects should be short and written in the imperative mood, such as "add", "fix", or "restore". Do not end the subject with a period.

For breaking changes, add a footer that starts with `BREAKING CHANGE:` and explains the migration path.

For reverts, start with `revert:` and include the commit being reverted in the body.
