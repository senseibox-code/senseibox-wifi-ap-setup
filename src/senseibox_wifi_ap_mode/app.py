from __future__ import annotations

import argparse
import os
import json
import logging
import threading
from dataclasses import dataclass
from dataclasses import asdict
from importlib import metadata
from pathlib import Path
from typing import Any

import uvicorn
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from .ap_mode import DEFAULT_STATE_DIR
from .network import NetworkManagerClient
from .service import WifiSetupService

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "static"
VERSION_FILE = ROOT / "VERSION"
DEFAULT_CONFIG_PATH = DEFAULT_STATE_DIR / "network.json"
LOGGER = logging.getLogger("senseibox_wifi_ap_mode")


def _exit_after_response() -> None:
    threading.Timer(1.0, lambda: os._exit(0)).start()


def app_version() -> str:
    try:
        version = VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        try:
            return metadata.version("senseibox-wifi-ap-mode")
        except metadata.PackageNotFoundError:
            return "0.0.0"
    return version or "0.0.0"


@dataclass(frozen=True)
class WifiConfigStore:
    path: Path

    @classmethod
    def from_environment(cls) -> "WifiConfigStore":
        configured = os.environ.get("SENSEIBOX_WIFI_CONFIG")
        return cls(Path(configured) if configured else DEFAULT_CONFIG_PATH)

    def write(self, ssid: str, password: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ssid": ssid,
            "password": password,
        }
        tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp_path, self.path)
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.path.exists(),
            "path": str(self.path),
        }


def _bad_request(message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=400)


async def homepage(_request: Request) -> FileResponse:
    return FileResponse(STATIC / "index.html")


async def api_version(_request: Request) -> JSONResponse:
    return JSONResponse({"version": app_version()})


async def api_status(request: Request) -> JSONResponse:
    store: WifiConfigStore = request.app.state.config_store
    service: WifiSetupService | None = request.app.state.setup_service
    payload = store.status()
    if service is not None:
        payload["state"] = service.state.name
        payload["ap_interface"] = service.state.ap_interface.name if service.state.ap_interface else None
        payload["last_error"] = service.state.last_error
        payload["setup_timeout_seconds"] = service.state.setup_deadline_seconds
    return JSONResponse(payload)


async def api_networks(request: Request) -> JSONResponse:
    network_manager: NetworkManagerClient = request.app.state.network_manager
    try:
        networks = network_manager.scan_wifi()
    except Exception:
        LOGGER.exception("Wi-Fi scan failed.")
        return JSONResponse({"error": "Unable to scan Wi-Fi networks."}, status_code=502)
    return JSONResponse({"networks": [asdict(network) for network in networks]})


async def api_configure_wifi(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return _bad_request("Request body must be valid JSON.")

    ssid = str(payload.get("ssid", "")).strip()
    password = str(payload.get("password", ""))

    if not ssid:
        return _bad_request("SSID is required.")
    if len(password) < 8:
        return _bad_request("Wi-Fi password must be at least 8 characters.")

    store: WifiConfigStore = request.app.state.config_store
    if request.app.state.connect_on_submit:
        service: WifiSetupService = request.app.state.setup_service
        network_manager: NetworkManagerClient = request.app.state.network_manager
        interface = service.state.ap_interface or network_manager.select_ap_interface()
        if interface is not None:
            service.stop_setup_mode()
        service.state.name = "connecting_to_wifi"
        LOGGER.info("Wi-Fi credentials submitted; attempting connection to selected network.")
        connected = network_manager.connect_wifi(ssid, password, interface.name if interface else None)
        if not connected:
            service.state.name = "wifi_failure"
            service.state.last_error = "Wi-Fi connection attempt failed."
            LOGGER.warning("Wi-Fi connection attempt failed; restarting setup AP mode.")
            if interface is not None:
                try:
                    service.restart_setup_mode(interface)
                except Exception:
                    LOGGER.exception("Failed to restart setup AP mode after Wi-Fi failure.")
            return JSONResponse({"saved": False, "connected": False, "error": "Unable to connect to Wi-Fi."}, status_code=502)
        service.state.name = "setup_complete"

    store.write(ssid, password)
    payload: dict[str, bool] = {"saved": True}
    if request.app.state.connect_on_submit:
        payload["connected"] = True
        return JSONResponse(payload, background=BackgroundTask(_exit_after_response))
    return JSONResponse(payload)


def create_app(
    config_store: WifiConfigStore | None = None,
    *,
    network_manager: NetworkManagerClient | None = None,
    setup_service: WifiSetupService | None = None,
    connect_on_submit: bool = False,
) -> Starlette:
    app = Starlette(
        debug=False,
        routes=[
            Route("/", homepage),
            Route("/api/version", api_version),
            Route("/api/status", api_status),
            Route("/api/networks", api_networks),
            Route("/api/wifi", api_configure_wifi, methods=["POST"]),
            Mount("/static", StaticFiles(directory=STATIC), name="static"),
        ],
    )
    app.state.config_store = config_store or WifiConfigStore.from_environment()
    app.state.network_manager = network_manager or NetworkManagerClient()
    app.state.setup_service = setup_service
    app.state.connect_on_submit = connect_on_submit
    return app


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Senseibox Wi-Fi AP onboarding service.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8080, type=int)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--boot", action="store_true", help="Exit if networking is already healthy.")
    parser.add_argument("--web-only", action="store_true", help="Run only the web app without AP setup control.")
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    parser.add_argument(
        "--setup-timeout-seconds",
        default=int(os.environ.get("SENSEIBOX_SETUP_TIMEOUT_SECONDS", "600")),
        type=int,
        help="Seconds to keep AP setup mode running before shutting it down.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    app_instance = app
    if not args.web_only:
        service = WifiSetupService(
            state_dir=Path(args.state_dir),
            setup_timeout_seconds=args.setup_timeout_seconds,
        )
        if args.boot and service.networking_healthy():
            return
        service.prepare_setup_mode()
        app_instance = create_app(
            setup_service=service,
            network_manager=service.network_manager,
            connect_on_submit=True,
        )

    uvicorn.run(
        app_instance,
        host=args.host,
        port=args.port,
        reload=args.reload,
        access_log=False,
    )


if __name__ == "__main__":
    main()
