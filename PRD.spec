# Senseibox Wi-Fi AP Mode Product Requirements

## Purpose

Senseibox Wi-Fi AP Mode is a Python-based onboarding service that helps a Senseibox device join a user's Wi-Fi network when no usable network connection is available.

The service runs on every boot, checks whether the device already has healthy networking, and exits without changing anything when networking is healthy. When setup is needed, it starts a temporary Wi-Fi access point, serves a local setup page, saves the selected Wi-Fi credentials safely, disables AP mode, and connects the device to the selected network. If the connection fails, it restarts AP mode and shows a clear error so the user can try again.

This file is the product and implementation guide for the service. If requirements change, update this file in the same change as the implementation.

## Goals

- Run automatically on every boot.
- Avoid AP mode when Ethernet or Wi-Fi networking is already usable.
- Recover gracefully when saved Wi-Fi credentials stop working.
- Provide a simple local setup page for selecting and joining Wi-Fi.
- Save credentials safely without leaking passwords into logs or shell command strings.
- Avoid leaving the device in a broken intermediate network state.
- Follow Senseibox deployment conventions under `/opt/senseibox/senseibox-wifi-ap-mode`.

## Non-Goals

- This service is not the primary network health dashboard for the product.
- This service should not force setup mode solely because public internet access is unavailable when local LAN access is working.
- This service should not delete existing Wi-Fi profiles until replacement credentials have connected successfully.

## Boot-Time User Experience

1. The user connects Senseibox to power.
2. Linux boots.
3. `senseibox-wifi-ap-mode.service` starts.
4. The service checks whether there is a usable wired connection.
5. If wired networking is usable, the service exits.
6. If wired networking is not usable, the service checks whether Wi-Fi is connected.
7. If Wi-Fi is connected, the service checks whether the Wi-Fi network is usable.
8. If Wi-Fi is connected and usable, the service exits.
9. If Wi-Fi is not connected, the service starts AP mode.
10. If Wi-Fi is connected but unusable, the service starts AP mode without deleting the existing profile.
11. The user connects to the temporary Senseibox setup network.
12. The user opens the setup page.
13. The setup page shows available Wi-Fi networks.
14. The user selects a Wi-Fi network and enters the password.
15. The service saves the submitted credentials as pending credentials.
16. The service disables AP mode.
17. The service tries to connect Senseibox to the selected Wi-Fi network.
18. If the connection succeeds, the service promotes the pending credentials and exits.
19. If the connection fails, the service restarts AP mode and shows an error.

## Service Lifetime

The service must run on every boot. It must not be treated as a one-shot first-boot-only service.

Rationale: users may need setup mode again when a router changes, a Wi-Fi password changes, a saved network no longer exists, a previous Wi-Fi connection becomes unusable, or the device is moved to a new location.

The service should exit once networking is healthy. It should keep running only while AP setup is active or while it is attempting to connect using newly submitted credentials.

## Network Usability

The service must not rely only on "Wi-Fi connected" status. A device can be associated with an access point while still having no usable network.

A network is considered usable when all required checks pass:

- The relevant interface has an IP address.
- The device has a default route when required by the connection type.
- DNS resolution works when DNS is required for the target mode.
- Local network access works.
- At least one configured test endpoint can be reached when endpoint checks are enabled.

Ethernet behavior:

- Check wired Ethernet before Wi-Fi.
- If Ethernet provides working LAN access, exit.
- Do not force AP mode only because the public internet is unavailable.
- Internet availability may be reported by a separate product surface.

Wi-Fi behavior:

- If Wi-Fi is connected and usable, exit.
- If Wi-Fi is not connected, start AP mode.
- If Wi-Fi is connected but unusable, mark the connection as failed for this boot and start AP mode.
- Do not immediately delete the old Wi-Fi connection.
- Replace the old connection only after new credentials connect successfully.

## Retry and Timeout Requirements

The service must not make a final setup-mode decision immediately after boot because interfaces can take time to initialize.

Recommended boot check flow:

1. Check Ethernet.
2. Wait 5 seconds.
3. Check Ethernet again.
4. Check Wi-Fi.
5. Wait 5 seconds.
6. Check Wi-Fi again.
7. Start AP mode only if all checks fail.

Maximum timeouts:

- Network boot checks: 60 seconds.
- DNS check: 5 seconds.
- Endpoint reachability check: 5 seconds.
- Wi-Fi connection attempt: 60 seconds.
- AP start attempt: 30 seconds.

All external command execution and network probes must have explicit timeouts.

## AP Mode Requirements

When no usable network exists, the service starts AP mode.

The AP must provide:

- Wi-Fi SSID.
- DHCP.
- Local gateway IP.
- Local setup page.
- Optional DNS redirect for captive portal behavior.

Recommended AP defaults:

- SSID: `Senseibox Setup`.
- Gateway IP: configurable setup gateway address.
- Setup URL: configurable setup gateway URL.
- Friendly URL: `http://senseibox.local/wifi`.
- DHCP range: configurable setup subnet range.

The setup gateway IP must always work directly. Do not rely only on `senseibox.local`, because some devices may not resolve mDNS correctly.

## AP Security

Avoid an open Wi-Fi setup network for production.

Preferred production options:

- Use a default setup password printed on the device label or included in the box.
- Use a device-specific setup password generated from a serial number or factory configuration.

Open AP mode is acceptable only for prototypes and local development. Production builds must require an AP password unless an explicit product decision says otherwise.

## Setup Page Requirements

Before implementing or substantially changing the web app UI, ask the product owner for the current designs. The setup page should reuse Senseibox KPI app UI code, styling conventions, and interaction patterns where practical because the Wi-Fi setup UI is expected to look similar.

The setup page must show:

- Senseibox name.
- Current network status.
- Available Wi-Fi networks.
- Signal strength.
- Security type.
- Password field.
- Manual SSID input for hidden networks.
- Connect button.
- Clear success and failure messages.

The page should stay simple and focused. It is a setup tool, not a marketing page.

## Wi-Fi Scanning Requirements

The service must scan nearby Wi-Fi networks and return:

- SSID.
- Signal strength.
- Security type.
- Frequency band, if available.
- Whether the network is currently connected.

The UI must sort networks by signal strength. It should hide duplicate SSIDs when possible, or show the strongest duplicate first.

## Hidden Network Support

The setup page must include an "Enter network name manually" path.

Manual network setup must support:

- SSID.
- Password.
- Security type, if needed.

## Password Handling

Wi-Fi passwords can contain spaces, quotes, symbols, and Unicode characters. The service must preserve them exactly.

Do not log Wi-Fi passwords.

Do not build shell commands with string concatenation.

Bad pattern:

```bash
nmcli dev wifi connect "$SSID" password "$PASSWORD"
```

Preferred pattern in Python:

```python
import subprocess

subprocess.run(
    ["nmcli", "dev", "wifi", "connect", ssid, "password", password],
    check=True,
    timeout=60,
)
```

Prefer structured APIs where available. If subprocess calls are used, pass argv lists and explicit timeouts.

## Network Stack

Recommended stack:

- NetworkManager for normal Wi-Fi client mode.
- `hostapd` for AP mode.
- `dnsmasq` for DHCP in AP mode.
- Python web app for the setup page.

NetworkManager is preferred because it works well on Debian, Ubuntu, and Armbian, supports scanning and saved connections, and is easier to operate safely than direct `wpa_supplicant` management.

## Systemd Requirements

Service name:

```text
senseibox-wifi-ap-mode.service
```

Behavior:

1. Start after NetworkManager.
2. Check Ethernet.
3. Check Wi-Fi.
4. Exit if networking is healthy.
5. Start AP mode if networking is not healthy.
6. Keep running while AP setup is active.
7. Exit after successful Wi-Fi connection.

The service should not block normal boot longer than necessary.

## Manual Recovery

Users need a way to force setup mode again.

Manual command:

```bash
senseibox-wifi-ap-mode
```

Expected behavior:

1. Stop the current Wi-Fi connection if needed.
2. Start AP mode.
3. Serve the setup page again.

This is required for router changes, password changes, and device relocation.

## Logging

Use journald as the main logging system.

Users should be able to debug with:

```bash
journalctl -u senseibox-wifi-ap-mode.service
```

Optional log file:

```text
/var/log/senseibox-wifi-setup.log
```

Logs must include:

- Service started.
- Ethernet check result.
- Wi-Fi check result.
- DNS check result.
- AP mode started.
- Setup page started.
- Credentials submitted.
- Wi-Fi connection attempt started.
- Wi-Fi connection succeeded.
- Wi-Fi connection failed.
- AP mode restarted after failure.

Logs must never include Wi-Fi passwords.

## Failure Handling

The service must never leave the device in a broken network state.

Avoid these failure modes:

- Wi-Fi disabled permanently.
- AP mode half-started.
- DHCP server not running.
- `hostapd` running without DHCP.
- NetworkManager fighting with `hostapd`.
- Old Wi-Fi credentials deleted too early.
- Setup page running without AP mode.
- AP mode running without the setup page.

Startup, shutdown, and failure paths must clean up partially started AP mode components.

## Internal State Model

Use an explicit state model to make the service easy to debug and test.

Recommended states:

```text
checking_network
wired_connected
wifi_connected
wifi_failed
starting_ap
ap_running
credentials_submitted
connecting_to_wifi
wifi_success
wifi_failure
setup_complete
```

State transitions should be logged without exposing secrets.

## Versioning and Operations

The service must expose:

```text
GET /api/version
```

Response:

```json
{"version":"0.1.0"}
```

The version should be read from the root `VERSION` file first and fall back to package metadata if the file cannot be read.

The installer and systemd unit must follow Senseibox conventions:

- Install under `/opt/senseibox/senseibox-wifi-ap-mode`.
- Run as the no-login `senseibox:senseibox` service account.
- Use a virtualenv under `/opt/senseibox/senseibox-wifi-ap-mode/.venv`.
- Install the tracked systemd unit from `systemd/senseibox-wifi-ap-mode.service`.
- Install required Debian runtime packages, including `python3`, `python3-venv`, `rsync`, `network-manager`, `hostapd`, `dnsmasq`, and Wi-Fi/network utility packages needed by the service.

## Acceptance Criteria

- On boot with usable Ethernet LAN access, the service exits without starting AP mode.
- On boot with usable Wi-Fi, the service exits without starting AP mode.
- On boot without usable networking, the service starts AP mode and serves the setup page.
- The setup page lists nearby Wi-Fi networks with signal and security metadata.
- The setup page supports manual hidden SSID entry.
- Submitted Wi-Fi passwords with spaces, quotes, symbols, and Unicode characters are preserved.
- The service attempts to connect using submitted credentials without unsafe shell interpolation.
- Existing Wi-Fi profiles are not deleted until replacement credentials succeed.
- Failed connection attempts return the device to AP setup mode.
- `GET /api/version` returns the current version.
- Logs contain useful state transitions and never include passwords.
- The systemd service runs as `senseibox:senseibox`.
- Installation works from both a source checkout and from the target install directory itself.

## Open Decisions

- Final web app designs for the setup flow.
- Whether production AP passwords are label-printed or device-specific.
- Exact setup gateway address and DHCP range values.
- Exact local LAN reachability check.
- Whether endpoint checks require internet access or only local product infrastructure.
- Whether captive portal DNS redirect is required for the first production release.
