from __future__ import annotations

from pathlib import Path

from senseibox_wifi_ap_mode.network import WifiNetwork
from senseibox_wifi_ap_mode.network_cache import WifiNetworkCache


def test_network_cache_round_trips_wifi_networks(tmp_path: Path):
    cache = WifiNetworkCache(tmp_path / "networks.json")

    cache.write(
        [
            WifiNetwork(
                ssid="Senseibox Lab",
                signal=90,
                security="WPA2",
                frequency="2412 MHz",
                connected=False,
            )
        ]
    )

    assert cache.read() == [
        WifiNetwork(
            ssid="Senseibox Lab",
            signal=90,
            security="WPA2",
            frequency="2412 MHz",
            connected=False,
        )
    ]
