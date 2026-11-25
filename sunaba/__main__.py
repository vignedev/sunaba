def main() -> None:
  import argparse
  from collections.abc import Callable
  from pathlib import Path

  from sunaba import Sunaba

  # list of expansions/bwrap injections
  # tuple[0] -> n_args, tuple[1] -> args
  SunabaBwrapExpansions: dict[
    str, tuple[int, Callable[[Sunaba, list[str]], Sunaba]]
  ] = {
    "--pass": (1, lambda sandbox, args: sandbox.bind(args[0])),
    "--ro-pass": (1, lambda sandbox, args: sandbox.bind(args[0], readonly=True)),
    "--pass-try": (
      1,
      lambda sandbox, args: sandbox.bind(args[0], ignore_errors=True),
    ),
    "--ro-pass-try": (
      1,
      lambda sandbox, args: sandbox.bind(args[0], readonly=True, ignore_errors=True),
    ),
    "--dev-pass": (1, lambda sandbox, args: sandbox.dev_bind(args[0])),
    "--dev-pass-try": (
      1,
      lambda sandbox, args: sandbox.dev_bind(args[0], ignore_errors=True),
    ),
    "--pass-cwd": (0, lambda sandbox, args: sandbox.bind(Path.cwd()).chdir(Path.cwd())),
    "--pass-ro-cwd": (
      0,
      lambda sandbox, args: sandbox.bind(Path.cwd(), readonly=True).chdir(Path.cwd()),
    ),
  }

  def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
      description="simple, dirty and biased sandbox",
      formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
      "-H",
      "--homedir",
      help="Host location of Sandbox's homedir (if empty, ephemeral storage is used)",
      required=False,
    )
    parser.add_argument(
      "-d",
      "--display",
      action="store_true",
      help="Enable (both Wayland and X11)",
      required=False,
    )
    parser.add_argument(
      "-w",
      "--wayland",
      action="store_true",
      help="Enable Wayland",
      required=False,
    )
    parser.add_argument(
      "-x",
      "--x11",
      action="store_true",
      help="Enable X11",
      required=False,
    )
    parser.add_argument(
      "-a",
      "--audio",
      action="store_true",
      help="Enable audio (both Pipewire and PulseAudio",
    )
    parser.add_argument("-n", "--net", action="store_true", help="Enable network")
    parser.add_argument("-r", "--dri", action="store_true", help="Pass DRI devices")
    parser.add_argument("-i", "--input", action="store_true", help="Pass input devices")
    parser.add_argument(
      "-R",
      "--hidraw",
      action="store_true",
      help="Pass currently connected hidraw devices",
    )
    parser.add_argument(
      "-N", "--nvidia", action="store_true", help="Pass NVIDIA devices"
    )
    parser.add_argument("-D", "--drm", action="store_true", help="Pass DRM devices")
    parser.add_argument(
      "-v",
      "--verbose",
      action="store_true",
      help="Output the full Bubblewrap arguments",
    )
    parser.add_argument(
      "--dry-run",
      action="store_true",
      help="Do not run, only output the Bubblewrap arguments",
    )
    parser.add_argument(
      "command",
      nargs=argparse.REMAINDER,
      help="Command and arguments to run inside the sandbox",
    )

    parser.epilog = f"""
Arguments can be passed directly into the underlaying bwrap in by using --, such as:
  sunaba --display --audio -- --setenv GTK_DEBUG=interactive -- gtk3-demo
         \\__sunaba args__/  \\______ bwrap args ____________/    \\__ actual commands
Additionally, there are certain "helper" arguments that are expanded if used in the bwrap arguments sections, which are:
  {"\n  ".join(SunabaBwrapExpansions.keys())}
"""

    return parser

  parser = get_parser()
  sandbox = Sunaba()
  args = parser.parse_args()
  if not args.command:
    parser.error("missing command after '--'")

  if args.display or args.wayland or args.x11:
    sandbox.with_display(
      wayland=(args.display or args.wayland), x11=(args.display or args.x11)
    )
  if args.audio:
    sandbox.with_audio()
  if args.net:
    sandbox.enable_net()
  if args.dri:
    sandbox.pass_dri()
  if args.drm:
    sandbox.pass_drm()
  if args.input:
    sandbox.pass_input()
  if args.hidraw:
    sandbox.pass_hidraw()
  if args.nvidia:
    sandbox.with_nvidia()

  # find additional bwrap and sandbox commands
  command = args.command[1:]
  bwrap_argv = []
  sandboxed_cmd = []

  bwrap_argv_gate = "--" in command
  for arg in command:
    if bwrap_argv_gate:
      if arg == "--":  # only care about the first -- if multiple are present
        bwrap_argv_gate = not bwrap_argv_gate
      else:
        bwrap_argv.append(arg)
    else:
      sandboxed_cmd.append(arg)

  # compatibility with previous interpretation for --[ro-]bind[-try] args
  bwrap_cmd_groups = []
  collector = []
  for arg in bwrap_argv:
    if not arg.startswith("--"):
      collector.append(arg)
    else:
      if collector:
        bwrap_cmd_groups.append(collector)
      collector = [arg]
  if collector:
    bwrap_cmd_groups.append(collector)

  # parse individual groups and handle special cases
  bwrap_argv = []
  for group in bwrap_cmd_groups:
    command = group[0]
    if expansion := SunabaBwrapExpansions[command]:
      if (len(group) - 1) != expansion[0]:
        parser.error(f"invalid argument count for {command} (required {expansion[0]})")
      expansion[1](sandbox, group[1:])
    else:
      bwrap_argv.extend(group)
  sandbox._argv.extend(bwrap_argv)

  # just in case im still sane
  if args.verbose or args.dry_run:
    parser._print_message(str(sandbox) + "\n")
    if args.dry_run:
      parser.exit(0)

  # ensure that -- <command> actually exists & run
  if not sandboxed_cmd:
    parser.error("cannot have empty sandboxed command line")

  [arg0, *argv] = sandboxed_cmd
  sandbox.run(arg0, argv)


if __name__ == "__main__":
  main()
