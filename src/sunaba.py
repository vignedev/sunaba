#!/usr/bin/env python3
import logging
import os
from itertools import chain
from pathlib import Path
from typing import Self

import utils
from bwrap import Bwrap

logger = logging.getLogger("sunaba")


class Sunaba(Bwrap):
  def __init__(
    self,
    homedir: utils.StrPath | None = None,
    user: str | None = None,
    uid: int | None = None,
  ) -> None:
    super().__init__()

    # getting guest_info
    guest_user = os.environ.get("USER") if user is None else user
    assert guest_user, "could not determine USER"
    guest_home = Path(f"/home/{guest_user}").resolve()
    guest_uid = uid if uid is not None else os.getuid()
    guest_shell = os.environ.get("SHELL", "/bin/sh")

    # set up the homedir
    if homedir:
      host_home = Path(homedir).absolute()
      host_home.mkdir(exist_ok=True)
      self.bind(host_home, guest_home)
    else:
      self.tmpfs(guest_home)

    # common setup and fs layout
    self.append_arg("unshare-all")
    self.append_arg("die-with-parent")
    self.append_arg("new-session")  # not convenient for bash etc. but safer
    self.append_arg("clearenv")
    self.append_arg("dev", "/dev")
    self.append_arg("proc", "/proc")
    self.append_arg("tmpfs", "/tmp")
    self.symlink("/usr/lib", "/lib")
    self.symlink("/usr/lib", "/lib64")
    self.symlink("/usr/bin", "/bin")
    self.symlink("/usr/bin", "/sbin")
    self.symlink("/run", "/var/run")
    self.bind("/usr", readonly=True)

    self.append_arg("uid", str(guest_uid))
    self.append_arg("gid", str(guest_uid))

    self.bind("/sys/dev/char", readonly=True)

    # set common envvars
    self.set_env("USER", guest_user)
    self.set_env("HOME", str(guest_home))
    self.set_env("XDG_CACHE_HOME", str(guest_home / ".cache"))
    self.set_env("XDG_CONFIG_HOME", str(guest_home / ".config"))
    self.set_env("XDG_RUNTIME_DIR", f"/run/user/{guest_uid}")
    self.set_env("PATH", "/usr/local/sbin:/usr/local/bin:/usr/bin")

    self.set_env("LANG", "en_US.UTF-8")
    self.set_env("LANGUAGE", "en_US.UTS-8")
    self.set_env("LC_ALL", "C")

    term_env = os.environ.get("TERM")
    if term_env:
      self.set_env("TERM", term_env)

    # pass files considered to be safe
    for dir in [
      "/etc/profile",
      "/etc/profile.d",
      "/etc/bash.bashrc",
      "/etc/ld.so.cache",
      "/etc/ld.so.conf",
      "/etc/ld.so.conf.d",
      # certificates
      "/usr/share/ca-certificates",
      "/etc/ssl",
      "/etc/certificates",
    ]:
      self.bind(dir, ignore_errors=True, readonly=True)

    # virtual /etc files
    self.bind("/etc/fonts", readonly=True, ignore_errors=True)
    self.bind("/etc/localtime", readonly=True, ignore_errors=True)

    # /etc/{passwd,group,hosts} need to be passed
    self.file(
      "/etc/passwd",
      "\n".join(
        [
          f"{guest_user}:x:{guest_uid}:{guest_uid}::{guest_home}:{guest_shell}",
          "nobody:x:65534:65534:Nobody:/:/usr/bin/nologin",
        ]
      ).encode(),
    )
    self.file(
      "/etc/group",
      "\n".join(
        [
          f"{guest_user}:x:{guest_uid}:",
          "nobody:x:65534:",
        ]
      ).encode(),
    )
    self.file("/etc/hosts", b"127.0.0.1\tlocalhost\n")

  # audio
  def __enable_pipewire(self) -> Self:
    if pipewire_socket_name := utils.get_pipewire_socket_name():
      pipewire_socket = (
        Path(os.environ.get("PIPEWIRE_RUNTIME_DIR", utils.xdg_runtime_dir()))
        / pipewire_socket_name
      )

      if pipewire_socket.is_socket():
        self.bind(
          pipewire_socket, Path(f"/run/user/{os.getuid()}") / pipewire_socket_name
        )
    return self

  def __enable_pulseaudio(self) -> Self:
    if pulseaudio_socket := utils.get_pulseaudio_socket_path():
      pa_socket = Path(pulseaudio_socket.removeprefix("unix:"))
      if pa_socket.is_socket():
        self.bind(pa_socket, utils.xdg_runtime_dir() / "pulse" / "native")
      else:
        logger.warning(
          f"pa_socket=({pa_socket}) is not a socket, pulseaudio is not passed"
        )
    return self

  def with_audio(self, pipewire: bool = True, pulseaudio: bool = True) -> Self:
    if pipewire:
      self.__enable_pipewire()
    if pulseaudio:
      self.__enable_pulseaudio()
    return self

  # networking
  def enable_net(self, custom_resolvconf: bytes | None = None) -> Self:
    if custom_resolvconf:
      self.file("/etc/resolv.conf", custom_resolvconf)
    else:
      self.bind("/etc/resolv.conf", readonly=True)
    self.append_arg("share-net")
    return self

  # display
  def __enable_wayland(self) -> Self:
    if wayland_display := os.environ.get("WAYLAND_DISPLAY"):
      wayland_socket = utils.xdg_runtime_dir() / wayland_display
      if wayland_socket.is_socket():
        self.bind(wayland_socket, readonly=True)
        self.set_env("WAYLAND_DISPLAY", wayland_display)
      else:
        logger.warning("WAYLAND_DISPLAY is set, however its socket is not found")
        return self

      wayland_socket_lock = utils.xdg_runtime_dir() / (wayland_display + ".lock")
      if wayland_socket_lock.exists():
        self.bind(wayland_socket_lock, readonly=True)
    return self

  def __enable_x11(self) -> Self:
    if x11_display := os.environ.get("DISPLAY"):
      if not (x11_socket := utils.get_x11_socket()):
        logger.warning("DISPLAY is set, but socket is not found")
        return self

      self.set_env("DISPLAY", x11_display)
      self.bind(x11_socket)

      if xauthority := os.environ.get("XAUTHORITY"):
        self.bind(xauthority, readonly=True)
        self.set_env("XAUTHORITY", xauthority)
    return self

  def with_display(self, wayland: bool = True, x11: bool = True) -> Self:
    if wayland:
      self.__enable_wayland()
    if x11:
      self.__enable_x11()
    return self

  # raw-device blocks
  def pass_dri(self) -> Self:
    self.bind("/sys/devices", readonly=True)
    self.dev_bind("/dev/dri")
    return self

  def pass_drm(self) -> Self:
    self.bind("/sys/class/drm", readonly=True)
    return self

  def pass_input(self) -> Self:
    self.bind("/sys/class/input", readonly=True)
    self.dev_bind("/dev/input")
    return self

  def pass_hidraw(self) -> Self:
    self.bind("/sys/class/hidraw", readonly=True)
    for device in Path("/dev").glob("hidraw*"):
      self.dev_bind(device)
    return self

  # nvidia-specific
  def with_nvidia(self) -> Self:
    for entry in chain(
      Path("/dev").glob("nvidia*"), Path("/sys/module").glob("nvidia*")
    ):
      self.dev_bind(entry)
    return self
