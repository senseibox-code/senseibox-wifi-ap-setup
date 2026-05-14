from __future__ import annotations

from pathlib import Path

from senseibox_wifi_ap_mode.network import WirelessInterface
from senseibox_wifi_ap_mode.network import WifiNetwork
from senseibox_wifi_ap_mode.service import WifiSetupService


class FakeNetworkManager:
    def __init__(self, interface: WirelessInterface) -> None:
        self.interface = interface

    def select_ap_interface(self) -> WirelessInterface:
        return self.interface

    def scan_wifi(self) -> list[WifiNetwork]:
        return [
            WifiNetwork(
                ssid="Senseibox Lab",
                signal=90,
                security="WPA2",
                frequency="2412 MHz",
                connected=False,
            )
        ]


class FakeAccessPointManager:
    def __init__(self) -> None:
        self.started: list[str] = []
        self.stopped: list[str] = []

    def start(self, interface: WirelessInterface, _settings) -> None:
        self.started.append(interface.name)

    def stop(self, interface: str) -> None:
        self.stopped.append(interface)


def test_setup_timeout_state_is_set_and_cleared(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SENSEIBOX_AP_GATEWAY", "setup-gateway")
    monkeypatch.setenv("SENSEIBOX_AP_DHCP_START", "setup-start")
    monkeypatch.setenv("SENSEIBOX_AP_DHCP_END", "setup-end")
    monkeypatch.setenv("SENSEIBOX_AP_PASSPHRASE", "setup-password")
    interface = WirelessInterface("setup0", "phy0")
    ap_manager = FakeAccessPointManager()
    service = WifiSetupService(
        state_dir=tmp_path,
        network_manager=FakeNetworkManager(interface),
        ap_manager=ap_manager,
        setup_timeout_seconds=600,
    )

    selected = service.prepare_setup_mode()

    assert selected == interface
    assert service.state.name == "ap_running"
    assert service.state.setup_deadline_seconds == 600
    assert ap_manager.started == ["setup0"]

    service.stop_setup_mode()

    assert service.state.ap_interface is None
    assert service.state.setup_deadline_seconds is None
    assert ap_manager.stopped == ["setup0", "setup0"]


def test_setup_mode_caches_wifi_scan_before_ap_handoff(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SENSEIBOX_AP_GATEWAY", "setup-gateway")
    monkeypatch.setenv("SENSEIBOX_AP_DHCP_START", "setup-start")
    monkeypatch.setenv("SENSEIBOX_AP_DHCP_END", "setup-end")
    monkeypatch.setenv("SENSEIBOX_AP_PASSPHRASE", "setup-password")
    interface = WirelessInterface("setup0", "phy0")
    service = WifiSetupService(
        state_dir=tmp_path,
        network_manager=FakeNetworkManager(interface),
        ap_manager=FakeAccessPointManager(),
    )

    service.prepare_setup_mode()

    cached = service.network_cache.read()
    assert [network.ssid for network in cached] == ["Senseibox Lab"]
