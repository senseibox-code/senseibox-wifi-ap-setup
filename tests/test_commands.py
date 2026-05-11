from __future__ import annotations

from senseibox_wifi_ap_mode.commands import CommandRunner


def test_command_timeout_returns_generic_error():
    result = CommandRunner().run(
        ["/bin/sh", "-c", "sleep 2"],
        timeout=1,
    )

    assert result.returncode == 124
    assert result.stderr == "Command timed out."
