# sunaba

## WHY

I needed a relatively simple way to create sandboxed environments, which could not access my `$HOME` folders, external storage devices, or access the internet.

`bwrap` by itself allows you to do so already, however the command line to create such environments can be quite large, with most of the arguments being shared with other sanboxex. This script essentially provides helper bash functions to hasten the creation of such environments.

## SCRIPTING USAGE

Create a bash script, which sources the [`sunaba.sh`](./sunaba.sh) file. After that, you can call these functions to enable certain functionalities in the sandbox:

```bash
# Call the `common_env` first, if you want to use it.
common_env "$HOMEDIR"  # common settings for (my) environment
                       # - the "$HOMEDIR" becomes "/home/$USER" in the sandbox
                       # - passes '/bin' and '/usr'
                       # - passes '/etc/{passwd,profile/profile.d/bash.bashrc/bash_completion.d}
                       # - passes '/etc/{fonts,environment,localtime}'
                       # - passes CA certificates (from /usr/share/ca-certificates, /etc/{ssl,ca-certificates})
                       # - passses /sys/dev/char, /sys/devices
                       # - sets $TERM from terminal
                       # - applies '--die-with-parent'
                       # - sets UID/GID to 1000

# Functions that enable functionalities
enable_display         # enables X11/Wayland support
enable_audio           # enables PipeWire/pulseaudio
enable_net             # enables networking capabilities
enable_dbus            # enables DBUS system socket
                       # - warning, this passes the system bus socket!!
                       # - enable only if necessary

# Passes certain device files to the sandbox
pass_dri               # passes /dev/dri, /dev/nvidia* and /sys/devices
pass_input_devices     # passes the entirety of /dev/input

# The final call
execute "$CMD" "$ARGS" # runs the program at "$CMD" with "$ARGS"
                       # - "$CMD" is searched within the sandbox, not in host
```

If there are additional `bwrap` options you want to set (eg. environmental variables), you can use the provided helper functions:
```bash
arg "ARGUMENT"         # adds --ARGUMENT to the argv
ro-pass "X" "Y" "Z"    # adds --ro-bind "X" "X" for each of the listed paths
dev-pass "X" "Y" "Z"   # same as above, however with --dev-pass
pass "X" "Y" "Z"       # save as --ro-pass, however uses --bind instead (rw file access)
```

## EXAMPLES

Examples of the scripts that I use can be found within the [`examples`](./examples/) folder.

## EXECUTION USAGE

It is possible to use the `sunaba.sh` as a script directly, with the following syntax:
```console
$ ./sunaba.sh
usage: ./sunaba.sh [flags] -- <bwrap args> -- <command> [arguments]
       ./sunaba.sh [flags] -- <command> [arguments]

this script implicitly calls 'common_env' with '$SANDBOX_DIR' which will be set to '$HOME/.sandbox' by default
the flags can be the following:
    -d    enables X11/Wayland support
    -a    enabled PipeWire/pulseaudio support
    -n    enables networking capabilities
    -s    passes dbus system socket
    -r    passes all dri devices
    -i    passes all input devices
    -v    verbose (just dumps the argv before execution)
```


## DISCLAIMER

This script (mainly `common_env`) makes quite a lot of assumptions to how the Linux system is setup. Be aware that a intensive security audit was not performed, thus it may be possible to escape the sandbox (especially with `enable_dbus`).

## LICENSE

MIT