#!/usr/bin/env bash

# list of arguments that will be passed to bwrap
argv=()
function arg(){ argv+=("--$1" "${@:2}"); }
function _pass() {
	for p in "${@:2}"; do
		arg "$1" "$p" "$p"
	done
}
function pass() { _pass bind "$@"; }
function ro-pass() { _pass ro-bind "$@"; }
function dev-pass() { _pass dev-bind "$@"; }

function try-pass() { _pass bind-try "$@"; }
function try-ro-pass() { _pass ro-bind-try "$@"; }
function try-dev-pass() { _pass dev-bind-try "$@"; }

# enables networking capability
# usage: enable_net
function enable_net() {
	ro-pass '/etc/resolv.conf'
	arg share-net
}

# enables pipewire/pulse related files for audio
# usage: enable_audio
function enable_audio() {
	if [ -S "$XDG_RUNTIME_DIR/pipewire-0" ]; then
        ro-pass "$XDG_RUNTIME_DIR/pipewire-0"
    fi
    if [ -d "$XDG_RUNTIME_DIR/pulse" ]; then
        ro-pass "$XDG_RUNTIME_DIR/pulse"
    fi
}

# enables display support (should be both X11 and Wayland)
# usage: enable_display
function enable_display() {
	if [ ! -z "$DISPLAY" ]; then
		# arg bind "/tmp/.X11-unix/X${DISPLAY#:*}" "/tmp/.X11-unix/X${DISPLAY#:*}"
		DISPLAY_ID="$(grep -Pom1 '[0-9]+' <<< "$DISPLAY" | head -n 1)"
		pass "/tmp/.X11-unix/X${DISPLAY_ID#:*}"

		arg setenv 'DISPLAY' :"$DISPLAY_ID"

		ro-pass "$XAUTHORITY"
		arg setenv 'XAUTHORITY' "$XAUTHORITY"
	fi

	# for wayland
	if [ -S "$XDG_RUNTIME_DIR/wayland-0" ]; then 
		ro-pass "$XDG_RUNTIME_DIR/wayland-0"

		XAUTH_PATH="$(ls "$XDG_RUNTIME_DIR"/xauth_* | head -n 1)"
		ro-pass "$XAUTH_PATH"
		arg setenv 'XAUTHORITY' "$XAUTH_PATH"
	fi
}

# enables dbus suppoprt
# usage: enable_dbus
function enable_dbus() {
	ro-pass '/run/dbus'
	ro-pass '/etc/machine-id'
	ro-pass "$XDG_RUNTIME_DIR/bus"
	arg setenv 'DBUS_SESSION_BUS_ADDRESS' "unix:path=$XDG_RUNTIME_DIR/bus"
}

# passes DRI devices
# usage: pass_dri
function pass_dri() {
	ro-pass '/sys/devices'
	dev-pass '/dev/dri'
}

# passes NVIDIA related items
# usage: pass_nvidia
function pass_nvidia() {
	for i in '/dev/nvidia'*; do
		dev-pass "$i"
	done
	ro-pass '/sys/module/nvidia'
}

# common passthrough
# usage: common_env <host_homedir_replacement>
function common_env(){
	# if no homedir is set, fail
	if [ -z "$1" ]; then
		echo 'common_passthrough requires an argument of the home dir to sandbox' >&2
		return 1
	fi

	# ensure that path is existant and can work
	if ! mkdir -p "$1"; then
		echo 'failed to create the sandbox homedir' >&2
		return 1
	fi

	# clear slate
	arg clearenv

	# setup the default "fs"
	arg dev '/dev'
	arg proc '/proc'
	arg tmpfs '/tmp'
	ro-pass '/bin'
	arg symlink '/usr/lib' '/lib'
	arg symlink '/usr/lib' '/lib64'
	arg symlink '/run' '/var/run'
	ro-pass '/usr'

	# passing through /etc files
	ro-pass \
		'/etc/passwd' \
		'/etc/fonts' '/etc/environment' '/etc/localtime'

	# these file may or may not exist, so only try but don't fail
	try-ro-pass \
		'/etc/profile' '/etc/profile.d' '/etc/bash.bashrc'

	# set uid/gid to 1000
	arg uid 1000
	arg gid 1000

	# basic devices
	ro-pass '/sys/dev/char'
	arg bind "$1" "/home/$USER"

	# pass-through certificates
	ro-pass '/usr/share/ca-certificates'
	ro-pass '/etc/ssl'
	ro-pass '/etc/ca-certificates'

	# default home env + path (not exported due to profile.d not being loaded by default)
	arg setenv 'HOME' "/home/$USER"
	arg setenv 'XDG_CACHE_HOME' "/home/$USER/.cache"
	arg setenv 'XDG_CONFIG_HOME' "/home/$USER/.config"
	arg setenv 'XDG_RUNTIME_DIR' "$XDG_RUNTIME_DIR"
	arg setenv 'PATH' '/usr/local/sbin:/usr/local/bin:/usr/bin'

	# unshare everything
	arg unshare-all

	# default chdir to home dir
	arg chdir "/home/$USER"

	# pass appropriate terminal
	if [ ! -z "$TERM" ]; then 
		arg setenv 'TERM' "$TERM"
	fi

	# ensure everything dies with parent
	arg die-with-parent
}

# pass input devices
# usage: pass_input_devices
function pass_input_devices(){
	dev-pass "/dev/input"
}

# executes the bwrap with given arguments
# usage: execute <command> [...arguments]
function execute() {
	bwrap "${argv[@]}" -- "$@"
}

# 
#  sunaba.sh is used as a script
# 
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
	function print_help(){
		echo "usage: $0 [flags] -- <bwrap args> -- <command> [arguments]"
		echo "       $0 [flags] -- <command> [arguments]"
		echo ""
		echo "this script implicitly calls 'common_env' with '\$SANDBOX_DIR' which will be set to '\$HOME/.sandbox' by default"
		echo "the flags can be the following:"
		echo "    -d    enables X11/Wayland support"
		echo "    -a    enabled PipeWire/pulseaudio support"
		echo "    -n    enables networking capabilities"
		echo "    -s    passes dbus system socket"
		echo "    -r    passes all dri devices"
		echo "    -i    passes all input devices"
		echo "    -v    verbose (just dumps the argv before execution)"
		echo "    -h    displays this help and exits"
		echo "    -N    passes nvidia devices"
		echo ""
		echo "for convenience, these options were added to bwrap args:"
		echo "   --pass <path>     equivalent to '--bind <path> <path>'"
		echo "   --ro-pass <path>  the same as above, however with '--ro-bind'"
		exit 1
	}

	# if $SANDBOX_DIR is not specified, use the default in $HOME/.sandbox
	if [ -z "$SANDBOX_DIR" ]; then
		SANDBOX_DIR="$HOME/.sandbox"
	fi
	common_env "$SANDBOX_DIR"

	# VERBOSE just dumps the final arguments passed to bwrap
	VERBOSE=0

	# parse the flags (default)
	while getopts 'dansrihvN' option; do
		case "$option" in
			d) enable_display ;;
			a) enable_audio ;;
			n) enable_net ;;
			s) enable_dbus ;;
			r) pass_dri ;;
			i) pass_input_devices ;;
			h) print_help ;;
			v) VERBOSE=1 ;;
			N) pass_nvidia ;;
			*) echo "option=$option" ;;
		esac
	done

	# get the items past the flags
	shift "$((OPTIND-1))"
	if [ "$VERBOSE" -eq 1 ]; then echo ">> AFTER_OPTS: '$*'"; fi

	# has_bwrap_args == a double dash is found after the first '--'
	has_bwrap_args=0
	# arguments/items specified *before* the double-dash (could be bwrap args/command)
	group_argv=()
	for option in "$@"; do
		shift 1
		if [ "$option" = "--" ]; then
			has_bwrap_args=1
			break
		fi
		group_argv+=("$option")
	done

	# in case additional bwrap options are used
	# eg.: sunaba.sh -- bwrap -- command
	pass_next=0
	if [ "$has_bwrap_args" -eq 1 ]; then
		for bwrap_arg in "${group_argv[@]}"; do
			if [ "$pass_next" -eq 1 ]; then
				if [ ! -e "$bwrap_arg" ]; then
					echo "failed --[ro]-pass: could not resolve '$bwrap_arg'"
					exit 1
				fi
				argv+=("$bwrap_arg" "$bwrap_arg")
				pass_next=0
				continue
			elif [ "$bwrap_arg" = "--pass" ]; then
				argv+=("--bind")
				pass_next=1
				continue
			elif [ "$bwrap_arg" = "--ro-pass" ]; then
				argv+=("--ro-bind")
				pass_next=1
				continue
			fi

			argv+=("$bwrap_arg")
		done
	fi
	if [ "$pass_next" -eq 1 ]; then
		echo "failed --[ro]-pass: trailing option"
		exit 1
	fi

	# execution phase
	user_command=()
	if [ "$has_bwrap_args" -eq 1 ]; then
		user_command=("$@")
	else
		user_command=("${group_argv[@]}")
	fi
	if [ "$VERBOSE" -eq 1 ]; then echo ">> user_command: '${user_command[*]}'"; fi

	# display help if there is no command to be run
	if [ -z "${user_command[0]}" ]; then print_help; fi

	# execute the command
	if [ "$VERBOSE" -eq 1 ]; then echo ">> ARGV: '${argv[*]} -- ${user_command[*]}'"; fi
	execute "${user_command[@]}"
fi
