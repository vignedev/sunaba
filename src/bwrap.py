import os
from typing import Self as _Self

import utils

BWRAP_EXECUTABLE = "bwrap"


class Bwrap:
  argv: list[str]
  files: dict[int, bytes]

  def __init__(self) -> None:
    self.argv = []
    self.files = {}

  def append_arg(self, key: str, *values: str) -> _Self:
    self.argv.extend([f"--{key}", *values])
    return self

  # regular binders
  def __binder(
    self,
    name: str,
    src: utils.StrPath,
    dest: utils.StrPath,
    readonly: bool,
    ignore_errors: bool,
  ) -> _Self:
    arg = f"{'ro-' if readonly else ''}{name}{'-try' if ignore_errors else ''}"
    self.append_arg(arg, utils.abspath(src), utils.abspath(dest))
    return self

  def bind(
    self,
    src: utils.StrPath,
    dest: utils.StrPath | None = None,
    readonly: bool = False,
    ignore_errors: bool = False,
  ) -> _Self:
    return self.__binder(
      "bind", src=src, dest=dest or src, readonly=readonly, ignore_errors=ignore_errors
    )

  def dev_bind(
    self,
    src: utils.StrPath,
    dest: utils.StrPath | None = None,
    ignore_errors: bool = False,
  ) -> _Self:
    return self.__binder(
      "dev-bind", src=src, dest=dest or src, readonly=False, ignore_errors=ignore_errors
    )

  # environments
  def unset_env(self, key: str) -> _Self:
    self.append_arg("unsetenv", key)
    return self

  def set_env(self, key: str, var: str) -> _Self:
    self.append_arg("setenv", key, var)
    return self

  # other common functions
  def tmpfs(self, target: utils.StrPath) -> _Self:
    self.append_arg("tmpfs", utils.abspath(target))
    return self

  def symlink(self, src: utils.StrPath, dest: utils.StrPath) -> _Self:
    self.append_arg("symlink", utils.abspath(src), utils.abspath(dest))
    return self

  # arbitrary data from str
  def file(self, path: utils.StrPath, data: bytes) -> _Self:
    memfd = os.memfd_create(utils.abspath(path), flags=0)
    os.write(memfd, data)
    os.lseek(memfd, 0, os.SEEK_SET)
    os.set_inheritable(memfd, True)

    self.files[memfd] = data
    self.append_arg("file", str(memfd), utils.abspath(path))

    return self

  def __str__(self):
    import shlex

    lines = [BWRAP_EXECUTABLE]
    collector = []
    for arg in self.argv:
      if not arg.startswith("--"):
        collector.append(arg)
      else:
        if collector:
          lines.append("  " + shlex.join(collector))
        collector = [arg]

    return "\n".join(lines)

  # final runner
  def run(self, arg0: str, argv: list[str] | None = None):
    final = [BWRAP_EXECUTABLE, *self.argv, "--", arg0, *(argv or [])]
    os.execvp(BWRAP_EXECUTABLE, final)


__all__ = ["Bwrap"]
