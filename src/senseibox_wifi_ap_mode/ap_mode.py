from __future__ import annotations

import os
import secrets
import signal
from dataclasses import dataclass
from pathlib import Path

from .commands import CommandRunner
from .network import NetworkManagerClient, WirelessInterface


DEFAULT_STATE_DIR = Path("/opt/senseibox/senseibox-wifi-ap-mode/state")


@dataclass(frozen=True)
class AccessPointSettings:
    ssid: str
    passphrase: str
    gateway: str
    dhcp_start: str
    dhcp_end: str
    country_code: str = "GB"
    channel: int = 6
    hw_mode: str = "g"
    driver: str = "nl80211"
    netmask_bits: int = 24

    @classmethod
    def from_environment(cls, state_dir: Path = DEFAULT_STATE_DIR) -> "AccessPointSettings":
        return cls(
            ssid=os.environ.get("SENSEIBOX_AP_SSID", "Senseibox Setup"),
            passphrase=setup_passphrase(state_dir),
            gateway=_required_env("SENSEIBOX_AP_GATEWAY"),
            dhcp_start=_required_env("SENSEIBOX_AP_DHCP_START"),
            dhcp_end=_required_env("SENSEIBOX_AP_DHCP_END"),
            country_code=os.environ.get("SENSEIBOX_AP_COUNTRY", "GB"),
            channel=int(os.environ.get("SENSEIBOX_AP_CHANNEL", "6")),
        )

    def validate(self) -> None:
        for name, value in {
            "ssid": self.ssid,
            "passphrase": self.passphrase,
            "gateway": self.gateway,
            "dhcp_start": self.dhcp_start,
            "dhcp_end": self.dhcp_end,
            "country_code": self.country_code,
        }.items():
            if "\n" in value or "\r" in value:
                raise ValueError(f"{name} must not contain newlines.")
        if not 8 <= len(self.passphrase) <= 63:
            raise ValueError("AP passphrase must be between 8 and 63 characters.")
        if not 1 <= self.channel <= 14:
            raise ValueError("AP channel must be a valid 2.4 GHz channel.")


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set for AP setup mode.")
    return value


def setup_passphrase(state_dir: Path) -> str:
    configured = os.environ.get("SENSEIBOX_AP_PASSPHRASE")
    if configured:
        return configured
    path = state_dir / "setup-ap-passphrase"
    try:
        existing = path.read_text(encoding="utf-8").strip()
    except OSError:
        existing = ""
    if existing:
        return existing
    state_dir.mkdir(parents=True, exist_ok=True)
    generated = secrets.token_urlsafe(12)
    path.write_text(generated + "\n", encoding="utf-8")
    path.chmod(0o600)
    return generated


def render_hostapd_config(interface: str, settings: AccessPointSettings) -> str:
    settings.validate()
    return "\n".join(
        [
            f"interface={interface}",
            f"driver={settings.driver}",
            f"ssid={settings.ssid}",
            f"country_code={settings.country_code}",
            "ieee80211d=1",
            f"hw_mode={settings.hw_mode}",
            f"channel={settings.channel}",
            "auth_algs=1",
            "ignore_broadcast_ssid=0",
            "wpa=2",
            f"wpa_passphrase={settings.passphrase}",
            "wpa_key_mgmt=WPA-PSK",
            "rsn_pairwise=CCMP",
            "",
        ]
    )


def render_dnsmasq_config(
    interface: str,
    settings: AccessPointSettings,
    *,
    lease_file: str | Path = "dnsmasq.leases",
) -> str:
    settings.validate()
    return "\n".join(
        [
            f"interface={interface}",
            "bind-interfaces",
            "port=0",
            f"dhcp-leasefile={lease_file}",
            f"dhcp-range={settings.dhcp_start},{settings.dhcp_end},12h",
            "domain-needed",
            "bogus-priv",
            "",
        ]
    )


class AccessPointManager:
    def __init__(
        self,
        *,
        state_dir: Path = DEFAULT_STATE_DIR,
        runner: CommandRunner | None = None,
        network_manager: NetworkManagerClient | None = None,
    ) -> None:
        self.state_dir = state_dir
        self.runner = runner or CommandRunner()
        self.network_manager = network_manager or NetworkManagerClient(self.runner)

    @property
    def hostapd_config_path(self) -> Path:
        return self.state_dir / "hostapd.conf"

    @property
    def dnsmasq_config_path(self) -> Path:
        return self.state_dir / "dnsmasq.conf"

    @property
    def hostapd_pid_path(self) -> Path:
        return self.state_dir / "hostapd.pid"

    @property
    def dnsmasq_pid_path(self) -> Path:
        return self.state_dir / "dnsmasq.pid"

    def start(self, interface: WirelessInterface, settings: AccessPointSettings) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.stop(interface.name, restore_network_manager=False)
        self.network_manager.set_managed(interface.name, False)
        self.runner.run(["rfkill", "unblock", "wifi"], timeout=10)
        self.runner.run(["ip", "link", "set", interface.name, "down"], timeout=10, check=True)
        self.runner.run(["ip", "addr", "flush", "dev", interface.name], timeout=10, check=True)
        self.runner.run(
            ["ip", "addr", "add", f"{settings.gateway}/{settings.netmask_bits}", "dev", interface.name],
            timeout=10,
            check=True,
        )
        self.runner.run(["ip", "link", "set", interface.name, "up"], timeout=10, check=True)

        self.hostapd_config_path.write_text(render_hostapd_config(interface.name, settings), encoding="utf-8")
        self.dnsmasq_config_path.write_text(
            render_dnsmasq_config(interface.name, settings, lease_file=self.state_dir / "dnsmasq.leases"),
            encoding="utf-8",
        )

        try:
            self.runner.run(
                [
                    "dnsmasq",
                    f"--conf-file={self.dnsmasq_config_path}",
                    f"--pid-file={self.dnsmasq_pid_path}",
                ],
                timeout=10,
                check=True,
            )
            self.runner.run(
                ["hostapd", "-B", "-P", str(self.hostapd_pid_path), str(self.hostapd_config_path)],
                timeout=30,
                check=True,
            )
        except Exception:
            self.stop(interface.name)
            raise

    def stop(self, interface: str | None = None, *, restore_network_manager: bool = True) -> None:
        self._stop_pid(self.hostapd_pid_path)
        self._stop_pid(self.dnsmasq_pid_path)
        if interface:
            self.runner.run(["ip", "addr", "flush", "dev", interface], timeout=10)
            if restore_network_manager:
                self.network_manager.set_managed(interface, True)

    def _stop_pid(self, path: Path) -> None:
        try:
            pid_text = path.read_text(encoding="utf-8").strip()
            pid = int(pid_text)
        except (OSError, ValueError):
            return
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            path.unlink()
        except OSError:
            pass
