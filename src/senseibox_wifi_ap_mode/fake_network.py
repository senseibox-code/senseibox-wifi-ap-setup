from __future__ import annotations

from .network import WifiNetwork
from .network import WirelessInterface


class FakeNetworkManagerClient:
    """NetworkManager-compatible fake data source for development."""

    def scan_wifi(self) -> list[WifiNetwork]:
        return [
            WifiNetwork(
                ssid="Home_Network_5G",
                signal=94,
                security="WPA2",
                frequency="5180 MHz",
                connected=False,
            ),
            WifiNetwork(
                ssid="Home_Network_2G",
                signal=86,
                security="WPA2",
                frequency="2412 MHz",
                connected=False,
            ),
            WifiNetwork(
                ssid="Office_WiFi",
                signal=68,
                security="WPA2",
                frequency="2462 MHz",
                connected=False,
            ),
            WifiNetwork(
                ssid="Cafe_WiFi",
                signal=52,
                security="WPA2",
                frequency="2437 MHz",
                connected=False,
            ),
            WifiNetwork(
                ssid="Guest_Network",
                signal=38,
                security="WPA2",
                frequency="2412 MHz",
                connected=False,
            ),
            WifiNetwork(
                ssid="Studio_WiFi",
                signal=31,
                security="WPA2",
                frequency="2437 MHz",
                connected=False,
            ),
            WifiNetwork(
                ssid="Workshop_2G",
                signal=24,
                security="WPA2",
                frequency="2462 MHz",
                connected=False,
            ),
            WifiNetwork(
                ssid="Open_Setup_Test",
                signal=18,
                security="open",
                frequency="2412 MHz",
                connected=False,
            ),
        ]

    def select_ap_interface(self) -> WirelessInterface:
        return WirelessInterface(name="fake-wlan0", phy="phy0")

    def connect_wifi(self, ssid: str, password: str, interface: str | None = None) -> bool:
        _ = interface
        return bool(ssid and password and password != "wrong-password")
