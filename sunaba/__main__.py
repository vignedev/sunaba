def main() -> None:
  import argparse

  from sunaba import Sunaba

  def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="simple, dirty and biased sandbox")
    parser.add_argument(
      "-H",
      "--homedir",
      help="Host location of Sandbox's homedir (if empty, ephemeral storage is used)",
      required=False,
    )
    parser.add_argument(
      "-d",
      "--display",
      choices=("both", "x11", "wayland"),
      help="Enable (both Wayland and X11)",
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
    return parser

  parser = get_parser()
  sandbox = Sunaba()
  args = parser.parse_args()
  if not args.command:
    parser.error("missing command after '--'")

  if args.display:
    sandbox.with_display(
      wayland=args.display in ("both", "wayland"), x11=args.display in ("both", "x11")
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
    if command in (
      "--pass",
      "--ro-pass",
      "--pass-try",
      "--ro-pass-try",
      "--dev-pass",
      "--dev-pass-try",
    ):
      if len(group) > 2:
        parser.error(f"invalid argument count for {command}")
      target = group[1]
      if command == "--pass":
        sandbox.bind(target)
      elif command == "--ro-pass":
        sandbox.bind(target, readonly=True)
      elif command == "--pass-try":
        sandbox.bind(target, ignore_errors=True)
      elif command == "--ro-pass-try":
        sandbox.bind(target, readonly=True, ignore_errors=True)
      elif command == "--dev-pass":
        sandbox.dev_bind(target)
      elif command == "--dev-pass-try":
        sandbox.dev_bind(target, ignore_errors=True)
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
