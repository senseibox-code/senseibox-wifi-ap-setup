from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles


ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "static"
VERSION_FILE = ROOT / "VERSION"
DEFAULT_CONFIG_PATH = Path("/opt/senseibox/senseibox-wifi-ap-mode/state/network.json")


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
    return JSONResponse(store.status())


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
    store.write(ssid, password)
    return JSONResponse({"saved": True})


def create_app(config_store: WifiConfigStore | None = None) -> Starlette:
    app = Starlette(
        debug=False,
        routes=[
            Route("/", homepage),
            Route("/api/version", api_version),
            Route("/api/status", api_status),
            Route("/api/wifi", api_configure_wifi, methods=["POST"]),
            Mount("/static", StaticFiles(directory=STATIC), name="static"),
        ],
    )
    app.state.config_store = config_store or WifiConfigStore.from_environment()
    return app


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Senseibox Wi-Fi AP onboarding service.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8080, type=int)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    uvicorn.run(
        "senseibox_wifi_ap_mode.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        access_log=False,
    )


if __name__ == "__main__":
    main()
