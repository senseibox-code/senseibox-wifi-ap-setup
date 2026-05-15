from __future__ import annotations

from senseibox_wifi_ap_mode.network import (
    NetworkManagerClient,
    parse_iw_dev,
    parse_iw_supported_modes,
    parse_nmcli_wifi_list,
    select_ap_interface,
)
from senseibox_wifi_ap_mode.commands import CommandResult


class RecordingRunner:
    def __init__(self, responses: dict[tuple[str, ...], CommandResult] | None = None) -> None:
        self.commands: list[tuple[str, ...]] = []
        self.responses = responses or {}

    def run(self, args, *, timeout: int = 10, check: bool = False):
        _ = timeout
        _ = check
        command = tuple(args)
        self.commands.append(command)
        return self.responses.get(command, CommandResult(command, 0, "", ""))


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


def test_ap_selection_skips_reserved_client_interface():
    iw_dev = """
phy#0
	Interface sta0
		type managed
	Interface wlan0
		type managed
"""
    iw_list = """
Wiphy phy0
	Supported interface modes:
		 * managed
		 * AP
"""

    selected = select_ap_interface(parse_iw_dev(iw_dev), parse_iw_supported_modes(iw_list))

    assert selected is not None
    assert selected.name == "wlan0"


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


def test_connect_wifi_unbinds_validated_profile_from_client_interface():
    network_manager = NetworkManagerClient(RecordingRunner())
    connection_name = network_manager._setup_connection_name("Home Network")
    active_command = ("nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active")
    saved_connections_command = ("nmcli", "-t", "-f", "NAME,802-11-wireless.ssid", "connection", "show")
    runner = RecordingRunner(
        {
            active_command: CommandResult(active_command, 0, f"{connection_name}:sta0\n", ""),
            saved_connections_command: CommandResult(
                saved_connections_command,
                0,
                f"{connection_name}:Home Network\nBroken Home Network:Home Network\nWired:\n",
                "",
            ),
        }
    )
    network_manager = NetworkManagerClient(runner)

    connected = network_manager.connect_wifi("Home Network", "test-password", "sta0")

    assert connected is True
    assert network_manager.last_connection_name == connection_name
    assert ("nmcli", "connection", "delete", connection_name) in runner.commands
    assert (
        "nmcli",
        "device",
        "wifi",
        "connect",
        "Home Network",
        "password",
        "test-password",
        "ifname",
        "sta0",
        "name",
        connection_name,
    ) in runner.commands
    assert ("nmcli", "connection", "modify", connection_name, "connection.interface-name", "") in runner.commands
    assert ("nmcli", "connection", "modify", connection_name, "connection.autoconnect", "yes") in runner.commands
    assert ("nmcli", "connection", "delete", "Broken Home Network") in runner.commands
