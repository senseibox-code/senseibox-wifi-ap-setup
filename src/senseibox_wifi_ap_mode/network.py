from __future__ import annotations

from dataclasses import dataclass

from .commands import CommandRunner


@dataclass(frozen=True)
class WirelessInterface:
    name: str
    phy: str | None = None


@dataclass(frozen=True)
class WifiNetwork:
    ssid: str
    signal: int | None
    security: str
    frequency: str
    connected: bool


def parse_iw_dev(output: str) -> list[WirelessInterface]:
    interfaces: list[WirelessInterface] = []
    current_phy: str | None = None
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if line.startswith("phy#"):
            current_phy = f"phy{line.removeprefix('phy#')}"
        elif line.startswith("Interface "):
            name = line.removeprefix("Interface ").strip()
            if name:
                interfaces.append(WirelessInterface(name=name, phy=current_phy))
    return interfaces


def parse_iw_supported_modes(output: str) -> dict[str | None, set[str]]:
    modes: dict[str | None, set[str]] = {}
    current_phy: str | None = None
    in_modes = False
    for raw_line in output.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("Wiphy "):
            current_phy = stripped.removeprefix("Wiphy ").strip()
            modes.setdefault(current_phy, set())
            in_modes = False
            continue
        if stripped == "Supported interface modes:":
            modes.setdefault(current_phy, set())
            in_modes = True
            continue
        if in_modes and stripped.startswith("* "):
            modes.setdefault(current_phy, set()).add(stripped.removeprefix("* ").strip())
            continue
        if in_modes and stripped and not raw_line.startswith("\t"):
            in_modes = False
    return modes


def select_ap_interface(
    interfaces: list[WirelessInterface],
    supported_modes: dict[str | None, set[str]],
) -> WirelessInterface | None:
    for interface in interfaces:
        modes = supported_modes.get(interface.phy) or supported_modes.get(None) or set()
        if "AP" in modes:
            return interface
    return None


def _split_nmcli_fields(line: str) -> list[str]:
    fields: list[str] = []
    current: list[str] = []
    escaped = False
    for char in line:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(char)
    fields.append("".join(current))
    return fields


def parse_nmcli_wifi_list(output: str) -> list[WifiNetwork]:
    networks: dict[str, WifiNetwork] = {}
    for line in output.splitlines():
        if not line.strip():
            continue
        fields = _split_nmcli_fields(line)
        if len(fields) < 5:
            continue
        connected_marker, ssid, signal_text, security, frequency = fields[:5]
        if not ssid:
            continue
        try:
            signal = int(signal_text)
        except ValueError:
            signal = None
        network = WifiNetwork(
            ssid=ssid,
            signal=signal,
            security=security or "open",
            frequency=frequency,
            connected=connected_marker == "*",
        )
        current = networks.get(ssid)
        if current is None or (network.signal or -1) > (current.signal or -1):
            networks[ssid] = network
    return sorted(networks.values(), key=lambda item: item.signal or -1, reverse=True)


class NetworkManagerClient:
    def __init__(self, runner: CommandRunner | None = None) -> None:
        self.runner = runner or CommandRunner()

    def wireless_interfaces(self) -> list[WirelessInterface]:
        result = self.runner.run(["iw", "dev"], timeout=5)
        if not result.ok:
            return []
        return parse_iw_dev(result.stdout)

    def supported_modes(self) -> dict[str | None, set[str]]:
        result = self.runner.run(["iw", "list"], timeout=10)
        if not result.ok:
            return {}
        return parse_iw_supported_modes(result.stdout)

    def select_ap_interface(self) -> WirelessInterface | None:
        return select_ap_interface(self.wireless_interfaces(), self.supported_modes())

    def set_managed(self, interface: str, managed: bool) -> None:
        self.runner.run(
            ["nmcli", "device", "set", interface, "managed", "yes" if managed else "no"],
            timeout=10,
            check=True,
        )

    def scan_wifi(self) -> list[WifiNetwork]:
        result = self.runner.run(
            [
                "nmcli",
                "-t",
                "-f",
                "IN-USE,SSID,SIGNAL,SECURITY,FREQ",
                "device",
                "wifi",
                "list",
                "--rescan",
                "yes",
            ],
            timeout=20,
            check=True,
        )
        return parse_nmcli_wifi_list(result.stdout)

    def connect_wifi(self, ssid: str, password: str, interface: str | None = None) -> bool:
        args = ["nmcli", "device", "wifi", "connect", ssid, "password", password]
        if interface:
            args.extend(["ifname", interface])
        result = self.runner.run(args, timeout=60)
        return result.ok

    def device_status(self) -> list[dict[str, str]]:
        result = self.runner.run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"], timeout=10)
        if not result.ok:
            return []
        devices: list[dict[str, str]] = []
        for line in result.stdout.splitlines():
            fields = _split_nmcli_fields(line)
            if len(fields) >= 3:
                devices.append({"device": fields[0], "type": fields[1], "state": fields[2]})
        return devices


class NetworkProbe:
    def __init__(self, runner: CommandRunner | None = None) -> None:
        self.runner = runner or CommandRunner()

    def has_ip_address(self, interface: str) -> bool:
        result = self.runner.run(["ip", "-4", "addr", "show", "dev", interface], timeout=5)
        return result.ok and "inet " in result.stdout

    def has_default_route(self, interface: str) -> bool:
        result = self.runner.run(["ip", "route", "show", "default", "dev", interface], timeout=5)
        return result.ok and bool(result.stdout.strip())

    def dns_works(self) -> bool:
        return self.runner.run(["getent", "hosts", "senseibox.de"], timeout=5).ok

    def wired_usable(self, devices: list[dict[str, str]]) -> bool:
        for device in devices:
            if device["type"] == "ethernet" and device["state"] == "connected":
                if self.has_ip_address(device["device"]):
                    return True
        return False

    def wifi_usable(self, devices: list[dict[str, str]]) -> bool:
        for device in devices:
            if device["type"] == "wifi" and device["state"] == "connected":
                if self.has_ip_address(device["device"]) and self.has_default_route(device["device"]):
                    return True
        return False
