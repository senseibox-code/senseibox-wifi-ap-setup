from __future__ import annotations

import json
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .network import WifiNetwork


@dataclass(frozen=True)
class WifiNetworkCache:
    path: Path

    def write(self, networks: list[WifiNetwork]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(network) for network in networks]
        tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(self.path)

    def read(self) -> list[WifiNetwork]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(payload, list):
            return []
        networks: list[WifiNetwork] = []
        for item in payload:
            network = _network_from_item(item)
            if network is not None:
                networks.append(network)
        return networks


def _network_from_item(item: Any) -> WifiNetwork | None:
    if not isinstance(item, dict):
        return None
    ssid = item.get("ssid")
    if not isinstance(ssid, str) or not ssid:
        return None
    signal = item.get("signal")
    if signal is not None and not isinstance(signal, int):
        signal = None
    security = item.get("security")
    frequency = item.get("frequency")
    connected = item.get("connected")
    return WifiNetwork(
        ssid=ssid,
        signal=signal,
        security=security if isinstance(security, str) else "open",
        frequency=frequency if isinstance(frequency, str) else "",
        connected=connected if isinstance(connected, bool) else False,
    )
