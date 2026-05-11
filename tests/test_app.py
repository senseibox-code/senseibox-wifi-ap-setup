from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

from senseibox_wifi_ap_mode.app import WifiConfigStore, create_app


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
