import json
import logging
import os
import re
import shutil
import subprocess
from functools import cache
from pathlib import Path

logger = logging.getLogger("utils")


def exec(*argv: str) -> str:
  return subprocess.run(argv, capture_output=True, text=True, check=True).stdout.strip()


def get_pipewire_socket_name() -> str | None:
  if not (pwdump := shutil.which("pw-dump")):
    logger.warning("pw-dump is not present, pipewire not passed")
    return None

  if not (stdout := exec(pwdump, "0")):
    return None

  data = json.loads(stdout)
  return data[0]["info"]["name"]


def get_pulseaudio_socket_path() -> str | None:
  if not (pactl := shutil.which("pactl")):
    logger.warning("pactl is not present, pulseaudio not passed")
    return None

  if not (stdout := exec(pactl, "info")):
    return None

  prefix = "Server String: "
  return next(
    (
      line.removeprefix(prefix).strip()
      for line in stdout.splitlines()
      if line.startswith(prefix)
    ),
    None,
  )


def get_x11_socket() -> str | None:
  if not (display := os.environ.get("DISPLAY")):
    return None

  if not (match := re.search(r":(\d+)(?:\.\d+)?$", display)):
    return None

  socket_path = Path("/tmp/.X11-unix") / f"X{match.group(1)}"
  return str(socket_path) if socket_path.is_socket() else None


@cache
def xdg_runtime_dir() -> Path:
  return Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))


@cache
def xdg_data_home() -> Path:
  if val := os.environ.get("XDG_DATA_HOME"):
    return Path(val)
  return Path.home() / ".local" / "share"
