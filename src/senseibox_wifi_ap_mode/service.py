from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Timer

from .ap import AccessPointManager, AccessPointSettings, DEFAULT_STATE_DIR
from .commands import CommandRunner
from .network import NetworkManagerClient, NetworkProbe, WirelessInterface


LOGGER = logging.getLogger("senseibox_wifi_ap_mode")


@dataclass
class ServiceState:
    name: str = "checking_network"
    ap_interface: WirelessInterface | None = None
    last_error: str | None = None
    setup_deadline_seconds: int | None = None


class WifiSetupService:
    def __init__(
        self,
        *,
        state_dir: Path = DEFAULT_STATE_DIR,
        runner: CommandRunner | None = None,
        network_manager: NetworkManagerClient | None = None,
        probe: NetworkProbe | None = None,
        ap_manager: AccessPointManager | None = None,
        setup_timeout_seconds: int = 600,
    ) -> None:
        self.state_dir = state_dir
        self.runner = runner or CommandRunner()
        self.network_manager = network_manager or NetworkManagerClient(self.runner)
        self.probe = probe or NetworkProbe(self.runner)
        self.ap_manager = ap_manager or AccessPointManager(
            state_dir=state_dir,
            runner=self.runner,
            network_manager=self.network_manager,
        )
        self.state = ServiceState()
        self.setup_timeout_seconds = setup_timeout_seconds
        self._setup_timer: Timer | None = None

    def networking_healthy(self, *, attempts: int = 6, delay: int = 5) -> bool:
        for attempt in range(attempts):
            devices = self.network_manager.device_status()
            if self.probe.wired_usable(devices):
                self.state.name = "wired_connected"
                LOGGER.info("Ethernet is usable; setup mode is not needed.")
                return True
            if self.probe.wifi_usable(devices):
                self.state.name = "wifi_connected"
                LOGGER.info("Wi-Fi is usable; setup mode is not needed.")
                return True
            if attempt + 1 < attempts:
                time.sleep(delay)
        self.state.name = "wifi_failed"
        LOGGER.info("No usable network detected; setup mode is needed.")
        return False

    def prepare_setup_mode(self) -> WirelessInterface:
        self.state.name = "starting_ap"
        interface = self.network_manager.select_ap_interface()
        if interface is None:
            self.state.last_error = "No Wi-Fi interface with AP mode support was found."
            raise RuntimeError(self.state.last_error)
        self.restart_setup_mode(interface)
        return interface

    def restart_setup_mode(self, interface: WirelessInterface) -> None:
        settings = AccessPointSettings.from_environment(self.state_dir)
        self.ap_manager.start(interface, settings)
        self.state.ap_interface = interface
        self.state.name = "ap_running"
        self.state.setup_deadline_seconds = self.setup_timeout_seconds
        self._start_setup_timeout()
        LOGGER.info("Setup AP mode started on interface %s.", interface.name)

    def stop_setup_mode(self) -> None:
        self._cancel_setup_timeout()
        if self.state.ap_interface is None:
            return
        self.ap_manager.stop(self.state.ap_interface.name)
        LOGGER.info("Setup AP mode stopped on interface %s.", self.state.ap_interface.name)
        self.state.ap_interface = None
        self.state.setup_deadline_seconds = None

    def _start_setup_timeout(self) -> None:
        self._cancel_setup_timeout()
        if self.setup_timeout_seconds <= 0:
            return
        self._setup_timer = Timer(self.setup_timeout_seconds, self._expire_setup_mode)
        self._setup_timer.daemon = True
        self._setup_timer.start()

    def _cancel_setup_timeout(self) -> None:
        if self._setup_timer is not None:
            self._setup_timer.cancel()
            self._setup_timer = None

    def _expire_setup_mode(self) -> None:
        self.state.name = "setup_timeout"
        self.state.last_error = "Setup timed out before Wi-Fi configuration completed."
        LOGGER.warning("Setup AP mode timed out; shutting down AP mode.")
        try:
            if self.state.ap_interface is not None:
                self.ap_manager.stop(self.state.ap_interface.name)
        finally:
            os._exit(0)
