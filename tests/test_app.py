from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

from senseibox_wifi_ap_mode.app import WifiConfigStore, create_app
from senseibox_wifi_ap_mode.fake_network import FakeNetworkManagerClient
from senseibox_wifi_ap_mode.network import WifiNetwork


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


def test_fake_network_mode_returns_design_networks(tmp_path: Path):
    client = TestClient(
        create_app(
            WifiConfigStore(tmp_path / "network.json"),
            network_manager=FakeNetworkManagerClient(),
        )
    )

    response = client.get("/api/networks")

    assert response.status_code == 200
    networks = response.json()["networks"]
    assert [network["ssid"] for network in networks] == [
        "Home_Network_5G",
        "Home_Network_2G",
        "Office_WiFi",
        "Cafe_WiFi",
        "Guest_Network",
    ]


def test_fake_network_mode_connects_without_ap_service(tmp_path: Path):
    config_path = tmp_path / "network.json"
    client = TestClient(
        create_app(
            WifiConfigStore(config_path),
            network_manager=FakeNetworkManagerClient(),
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
            network_manager=FakeNetworkManagerClient(),
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
