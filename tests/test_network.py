from __future__ import annotations

from senseibox_wifi_ap_mode.network import (
    parse_iw_dev,
    parse_iw_supported_modes,
    parse_nmcli_wifi_list,
    select_ap_interface,
)


def test_selects_first_wireless_interface_with_ap_support():
    iw_dev = """
phy#0
	Interface managed0
		type managed
phy#1
	Interface setup0
		type managed
"""
    iw_list = """
Wiphy phy0
	Supported interface modes:
		 * managed
Wiphy phy1
	Supported interface modes:
		 * managed
		 * AP
"""

    selected = select_ap_interface(parse_iw_dev(iw_dev), parse_iw_supported_modes(iw_list))

    assert selected is not None
    assert selected.name == "setup0"
    assert selected.phy == "phy1"


def test_nmcli_wifi_list_deduplicates_and_sorts_by_signal():
    output = "\n".join(
        [
            ":Lab\\:Network:40:WPA2:2412 MHz",
            "*:Office:65:WPA2:5180 MHz",
            ":Lab\\:Network:82:WPA2:2462 MHz",
            ":Open:20::2412 MHz",
        ]
    )

    networks = parse_nmcli_wifi_list(output)

    assert [network.ssid for network in networks] == ["Lab:Network", "Office", "Open"]
    assert networks[0].signal == 82
    assert networks[0].security == "WPA2"
    assert networks[1].connected is True
    assert networks[2].security == "open"
