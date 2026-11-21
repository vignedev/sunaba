import os
from typing import Self

from .utils import StrPath, abspath


class Bwrap:
  argv: list[str]
  files: dict[int, bytes]

  def __init__(self) -> None:
    self.argv = []
    self.files = {}

  def append_arg(self, key: str, *values: str) -> Self:
    self.argv.extend([f"--{key}", *values])
    return self

  # regular binders
  def __binder(
    self, name: str, src: StrPath, dest: StrPath, readonly: bool, ignore_errors: bool
  ) -> Self:
    arg = f"{'ro-' if readonly else ''}{name}{'-try' if ignore_errors else ''}"
    self.append_arg(arg, abspath(src), abspath(dest))
    return self

  def bind(
    self,
    src: StrPath,
    dest: StrPath | None = None,
    readonly: bool = False,
    ignore_errors: bool = False,
  ) -> Self:
    return self.__binder(
      "bind", src=src, dest=dest or src, readonly=readonly, ignore_errors=ignore_errors
    )

  def dev_bind(
    self, src: StrPath, dest: StrPath | None = None, ignore_errors: bool = False
  ) -> Self:
    return self.__binder(
      "dev-bind", src=src, dest=dest or src, readonly=False, ignore_errors=ignore_errors
    )

  # environments
  def unset_env(self, key: str) -> Self:
    self.append_arg("unsetenv", key)
    return self

  def set_env(self, key: str, var: str) -> Self:
    self.append_arg("setenv", key, var)
    return self

  # other common functions
  def tmpfs(self, target: StrPath) -> Self:
    self.append_arg("tmpfs", abspath(target))
    return self

  def symlink(self, src: StrPath, dest: StrPath) -> Self:
    self.append_arg("symlink", abspath(src), abspath(dest))
    return self

  # arbitrary data from str
  def file(self, path: StrPath, data: bytes) -> Self:
    memfd = os.memfd_create(abspath(path), flags=0)
    os.write(memfd, data)
    os.lseek(memfd, 0, os.SEEK_SET)
    os.set_inheritable(memfd, True)

    self.files[memfd] = data
    self.append_arg("file", str(memfd), abspath(path))

    return self

  # final runner
  def run(self, arg0: str, argv: list[str] | None = None):
    final = ["bwrap", *self.argv, "--", arg0, *(argv or [])]
    os.execvp("bwrap", final)
