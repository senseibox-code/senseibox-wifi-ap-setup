from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

from senseibox_wifi_ap_mode.app import DEV_CONFIG_PATH, WifiConfigStore, create_app
from senseibox_wifi_ap_mode.fake_network import FakeNetworkManagerClient
from senseibox_wifi_ap_mode.network import WifiNetwork
from senseibox_wifi_ap_mode.network_cache import WifiNetworkCache


class FakeNetworkManager:
    def scan_wifi(self):
        return [
            WifiNetwork(
                ssid="Senseibox Lab",
                signal=90,
                security="WPA2",
                frequency="2412 MHz",
                connected=False,
            )
        ]


class EmptyNetworkManager:
    def scan_wifi(self):
        return []


class ConnectTrackingNetworkManager:
    def __init__(self) -> None:
        self.connected_with: tuple[str, str, str | None] | None = None
        self.last_connection_name: str | None = None

    def scan_wifi(self):
        return []

    def connect_wifi(self, ssid: str, password: str, interface: str | None = None) -> bool:
        self.connected_with = (ssid, password, interface)
        self.last_connection_name = ssid
        return True

    def select_ap_interface(self):
        return None


class FakeSetupService:
    def __init__(self) -> None:
        self.state = type(
            "State",
            (),
            {
                "name": "ap_running",
                "ap_interface": None,
                "client_interface": type("Interface", (), {"name": "sta0"})(),
                "last_error": None,
                "setup_deadline_seconds": 600,
            },
        )()
        self.network_cache = WifiNetworkCache(Path("/missing/networks.json"))
        self.completed = False

    def complete_setup_mode(self) -> None:
        self.completed = True


def test_api_version():
    client = TestClient(create_app())

    response = client.get("/api/version")

    assert response.status_code == 200
    assert response.json() == {"version": "0.1.0"}


def test_wifi_credentials_are_saved(tmp_path: Path):
    config_path = tmp_path / "network.json"
    client = TestClient(create_app(WifiConfigStore(config_path)))

    response = client.post(
        "/api/wifi",
        json={"ssid": "Senseibox Lab", "password": "test-password"},
    )

    assert response.status_code == 200
    assert response.json() == {"saved": True}
    assert '"ssid": "Senseibox Lab"' in config_path.read_text(encoding="utf-8")


def test_wifi_configuration_requires_ssid(tmp_path: Path):
    client = TestClient(create_app(WifiConfigStore(tmp_path / "network.json")))

    response = client.post("/api/wifi", json={"ssid": "", "password": "test-password"})

    assert response.status_code == 400
    assert response.json() == {"error": "SSID is required."}


def test_wifi_save_failure_returns_safe_error(tmp_path: Path):
    blocked_parent = tmp_path / "state"
    blocked_parent.write_text("not a directory", encoding="utf-8")
    client = TestClient(create_app(WifiConfigStore(blocked_parent / "network.json")))

    response = client.post(
        "/api/wifi",
        json={"ssid": "Senseibox Lab", "password": "test-password"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "saved": False,
        "error": "Unable to save Wi-Fi credentials.",
    }


def test_api_networks_returns_scan_results(tmp_path: Path):
    client = TestClient(
        create_app(
            WifiConfigStore(tmp_path / "network.json"),
            network_manager=FakeNetworkManager(),
        )
    )

    response = client.get("/api/networks")

    assert response.status_code == 200
    assert response.json() == {
        "networks": [
            {
                "ssid": "Senseibox Lab",
                "signal": 90,
                "security": "WPA2",
                "frequency": "2412 MHz",
                "connected": False,
            }
        ]
    }


def test_api_networks_falls_back_to_cached_setup_scan(tmp_path: Path):
    cache = WifiNetworkCache(tmp_path / "networks.json")
    cache.write(
        [
            WifiNetwork(
                ssid="Cached Network",
                signal=80,
                security="WPA2",
                frequency="2462 MHz",
                connected=False,
            )
        ]
    )
    client = TestClient(
        create_app(
            WifiConfigStore(tmp_path / "network.json"),
            network_manager=EmptyNetworkManager(),
            network_cache=cache,
        )
    )

    response = client.get("/api/networks")

    assert response.status_code == 200
    assert response.json()["networks"][0]["ssid"] == "Cached Network"


def test_fake_network_mode_returns_design_networks(tmp_path: Path):
    client = TestClient(
        create_app(
            WifiConfigStore(tmp_path / "network.json"),
            network_manager=FakeNetworkManagerClient(scan_delay_seconds=0),
        )
    )

    response = client.get("/api/networks")

    assert response.status_code == 200
    networks = response.json()["networks"]
    assert [network["ssid"] for network in networks[:5]] == [
        "Home_Network_5G",
        "Home_Network_2G",
        "Office_WiFi",
        "Cafe_WiFi",
        "Guest_Network",
    ]
    assert len(networks) > 5


def test_fake_network_mode_defaults_to_development_scan_delay():
    assert FakeNetworkManagerClient().scan_delay_seconds == 6


def test_fake_network_development_store_uses_local_state_by_default(monkeypatch):
    monkeypatch.delenv("SENSEIBOX_WIFI_CONFIG", raising=False)

    store = WifiConfigStore.for_development()

    assert store.path == DEV_CONFIG_PATH


def test_fake_network_mode_connects_without_ap_service(tmp_path: Path):
    config_path = tmp_path / "network.json"
    client = TestClient(
        create_app(
            WifiConfigStore(config_path),
            network_manager=FakeNetworkManagerClient(scan_delay_seconds=0),
            connect_on_submit=True,
        )
    )

    response = client.post(
        "/api/wifi",
        json={"ssid": "Home_Network_5G", "password": "test-password"},
    )

    assert response.status_code == 200
    assert response.json() == {"saved": True, "connected": True}
    assert '"ssid": "Home_Network_5G"' in config_path.read_text(encoding="utf-8")


def test_fake_network_mode_can_return_connection_failure(tmp_path: Path):
    config_path = tmp_path / "network.json"
    client = TestClient(
        create_app(
            WifiConfigStore(config_path),
            network_manager=FakeNetworkManagerClient(scan_delay_seconds=0),
            connect_on_submit=True,
        )
    )

    response = client.post(
        "/api/wifi",
        json={"ssid": "Home_Network_5G", "password": "wrong-password"},
    )

    assert response.status_code == 502
    assert response.json() == {
        "saved": False,
        "connected": False,
        "error": "Unable to connect to Wi-Fi.",
    }
    assert not config_path.exists()


def test_real_setup_connects_on_client_interface_before_completing_setup(tmp_path: Path):
    config_path = tmp_path / "network.json"
    network_manager = ConnectTrackingNetworkManager()
    setup_service = FakeSetupService()
    client = TestClient(
        create_app(
            WifiConfigStore(config_path),
            network_manager=network_manager,
            setup_service=setup_service,
            connect_on_submit=True,
            exit_on_connect=True,
        )
    )

    response = client.post(
        "/api/wifi",
        json={"ssid": "Senseibox Lab", "password": "test-password"},
    )

    assert response.status_code == 200
    assert response.json() == {"saved": True, "connected": True}
    assert network_manager.connected_with == ("Senseibox Lab", "test-password", "sta0")
    assert setup_service.completed is True
