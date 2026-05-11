# Senseibox Wi-Fi AP Mode

Wi-Fi onboarding service for Senseibox. It starts a local setup page in access point mode, captures Wi-Fi credentials, and stores the network configuration for the device to use on reconnect.

## Install

```sh
sudo ./install.sh
```

The installer deploys the app to `/opt/senseibox/senseibox-wifi-ap-mode`, creates or reuses the shared no-login `senseibox:senseibox` service account, installs a virtualenv under `/opt/senseibox/senseibox-wifi-ap-mode/.venv`, and starts the `senseibox-wifi-ap-mode` systemd service.

It also installs the Debian runtime packages required for Wi-Fi setup and AP mode, including NetworkManager, `hostapd`, `dnsmasq`, Python venv support, `rsync`, and Wi-Fi/network utility packages.

The setup page listens on port `8080`:

```text
http://<senseibox-host>:8080/
```

## Operations

Check service status:

```sh
sudo systemctl status senseibox-wifi-ap-mode
```

Follow service logs:

```sh
sudo journalctl -u senseibox-wifi-ap-mode -f
```

Check AP support services and wireless diagnostics:

```sh
sudo systemctl status hostapd
```

```sh
ip a
```

```sh
iw dev
```

```sh
iw list
```

## API

`GET /api/version` returns the running app version:

```json
{"version":"0.1.0"}
```

`POST /api/wifi` accepts Wi-Fi credentials:

```json
{"ssid":"Network name","password":"network password"}
```

By default, saved Wi-Fi settings are written to `/opt/senseibox/senseibox-wifi-ap-mode/state/network.json` with owner-only permissions. Set `SENSEIBOX_WIFI_CONFIG` to override that path.
