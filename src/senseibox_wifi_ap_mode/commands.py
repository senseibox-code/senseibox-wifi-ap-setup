from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import subprocess


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class CommandRunner:
    def run(
        self,
        args: Sequence[str],
        *,
        timeout: int = 10,
        check: bool = False,
    ) -> CommandResult:
        try:
            completed = subprocess.run(
                list(args),
                capture_output=True,
                check=False,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return CommandResult(
                args=tuple(args),
                returncode=124,
                stdout="",
                stderr="Command timed out.",
            )
        result = CommandResult(
            args=tuple(args),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        if check and not result.ok:
            raise CommandFailed(result.returncode)
        return result


class CommandFailed(RuntimeError):
    def __init__(self, returncode: int) -> None:
        super().__init__(f"Command failed with exit code {returncode}.")
        self.returncode = returncode
