import os
from pathlib import Path
from typing import Self

type StrPath = str | os.PathLike[str]


class Bwrap:
  argv: list[str]
  files: dict[int, bytes]

  def __init__(self) -> None:
    self.argv = []
    self.files = {}

  def append_arg(self, key: str, *values: str) -> Self:
    self.argv.extend([f"--{key}", *values])
    return self

  def _resolve_path(self, path: StrPath) -> str:
    return str(Path(path).absolute())

  # regular binders
  def _binder(
    self, name: str, src: StrPath, dest: StrPath, readonly: bool, ignore_errors: bool
  ) -> Self:
    arg = f"{'ro-' if readonly else ''}{name}{'-try' if ignore_errors else ''}"
    self.append_arg(arg, self._resolve_path(src), self._resolve_path(dest))
    return self

  def bind(
    self,
    src: StrPath,
    dest: StrPath | None = None,
    readonly: bool = False,
    ignore_errors: bool = False,
  ) -> Self:
    return self._binder(
      "bind", src=src, dest=dest or src, readonly=readonly, ignore_errors=ignore_errors
    )

  def dev_bind(
    self, src: StrPath, dest: StrPath | None = None, ignore_errors: bool = False
  ) -> Self:
    return self._binder(
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
    self.append_arg("tmpfs", self._resolve_path(target))
    return self

  def symlink(self, src: StrPath, dest: StrPath) -> Self:
    self.append_arg("symlink", self._resolve_path(src), self._resolve_path(dest))
    return self

  # arbitrary data from str
  def file(self, path: StrPath, data: bytes) -> Self:
    memfd = os.memfd_create(self._resolve_path(path), flags=0)
    os.write(memfd, data)
    os.lseek(memfd, 0, os.SEEK_SET)
    os.set_inheritable(memfd, True)

    self.files[memfd] = data
    self.append_arg("file", str(memfd), self._resolve_path(path))

    return self

  # final runner
  def run(self, arg0: str, argv: list[str] | None = None):
    final = ["bwrap", *self.argv, "--", arg0, *(argv or [])]
    os.execvp("bwrap", final)
