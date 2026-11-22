import os
import typing

from .utils import StrPath, abspath

BWRAP_EXECUTABLE = "bwrap"


class Bwrap:
  _argv: list[str]
  files: dict[int, bytes]
  environ: dict[str, str]

  def __init__(self) -> None:
    self._argv = []
    self.files = {}
    self.environ = {}

  def append_arg(self, key: str, *values: str) -> typing.Self:
    self._argv.extend([f"--{key}", *values])
    return self

  @property
  def arguments(self) -> list[str]:
    return [*self._argv, *self._environ_argv()]

  # regular binders
  def __binder(
    self,
    name: str,
    src: StrPath,
    dest: StrPath,
    readonly: bool,
    ignore_errors: bool,
  ) -> typing.Self:
    arg = f"{'ro-' if readonly else ''}{name}{'-try' if ignore_errors else ''}"
    self.append_arg(arg, abspath(src), abspath(dest))
    return self

  def bind(
    self,
    src: StrPath,
    dest: StrPath | None = None,
    readonly: bool = False,
    ignore_errors: bool = False,
  ) -> typing.Self:
    return self.__binder(
      "bind", src=src, dest=dest or src, readonly=readonly, ignore_errors=ignore_errors
    )

  def dev_bind(
    self,
    src: StrPath,
    dest: StrPath | None = None,
    ignore_errors: bool = False,
  ) -> typing.Self:
    return self.__binder(
      "dev-bind", src=src, dest=dest or src, readonly=False, ignore_errors=ignore_errors
    )

  # environments
  def unset_env(self, key: str) -> typing.Self:
    self.environ.pop(key, None)
    return self

  def set_env(self, key: str, var: str) -> typing.Self:
    self.environ[key] = var
    return self

  def get_env(self, key: str) -> str | None:
    return self.environ.get(key, None)

  def _environ_argv(self) -> list[str]:
    collector = []
    for key, value in self.environ.items():
      collector.extend(["--setenv", key, value])
    return collector

  # other common functions
  def tmpfs(self, target: StrPath) -> typing.Self:
    self.append_arg("tmpfs", abspath(target))
    return self

  def symlink(self, src: StrPath, dest: StrPath) -> typing.Self:
    self.append_arg("symlink", abspath(src), abspath(dest))
    return self

  # arbitrary data from str
  def file(self, path: StrPath, data: bytes) -> typing.Self:
    memfd = os.memfd_create(abspath(path), flags=0)
    os.write(memfd, data)
    os.lseek(memfd, 0, os.SEEK_SET)
    os.set_inheritable(memfd, True)

    self.files[memfd] = data
    self.append_arg("file", str(memfd), abspath(path))

    return self

  def __str__(self):
    import shlex

    lines = [BWRAP_EXECUTABLE]
    collector = []
    for arg in self.arguments:
      if not arg.startswith("--"):
        collector.append(arg)
      else:
        if collector:
          lines.append("  " + shlex.join(collector))
        collector = [arg]
    if collector:  # backflush
      lines.append("  " + shlex.join(collector))

    return "\n".join(lines)

  # final runner
  def run(self, arg0: str, argv: list[str] | None = None):
    final = [BWRAP_EXECUTABLE, *self.arguments, "--", arg0, *(argv or [])]
    os.execvp(BWRAP_EXECUTABLE, final)
