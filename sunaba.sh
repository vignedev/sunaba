#!/usr/bin/env bash

# list of arguments that will be passed to bwrap
argv=()
function arg(){
	argv+=("--$1" "${@:2}")
}
function ro-pass() {
	for p in "$@"; do
		arg ro-bind "$p" "$p"
	done
}
function dev-pass() {
	for p in "$@"; do
		arg dev-bind "$p" "$p"
	done
}
function pass() {
	for p in "$@"; do
		arg bind "$p" "$p"
	done
}

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
	for i in '/dev/nvidia'*; do
		dev-pass "$i"
	done
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
		'/etc/profile' '/etc/profile.d' \
		'/etc/bash.bashrc' \
		'/etc/fonts' '/etc/environment' '/etc/localtime'

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
		exit 1
	}

	if [ -z "$SANDBOX_DIR" ]; then
		SANDBOX_DIR="$HOME/.sandbox"
	fi

	common_env "$SANDBOX_DIR"

	VERBOSE=0
	while getopts 'hdansriv' option; do
		case "$option" in
			d) enable_display ;;
			a) enable_audio ;;
			n) enable_net ;;
			s) enable_dbus ;;
			r) pass_dri ;;
			i) pass_input_devices ;;
			h) print_help ;;
			v) VERBOSE=1 ;;
			*) echo "option=$option" ;;
		esac
	done

	shift "$((OPTIND-1))"
	if [ -z "$1" ]; then
		print_help
	fi
	
	if [ $VERBOSE -eq 1 ]; then
		echo ">> AFTER_OPTS: '$*"
	fi

	doubledash=0
	group_n=0
	group_argv=()

	for option in "$@"; do
		((group_n++))
		shift 1
		if [ "$option" = "--" ]; then
			doubledash=1
			break
		fi
		group_argv+=("$option")
	done

	# in case additional bwrap options are used
	if [ "$doubledash" -eq 1 ]; then # sunaba.sh -- bwrap -- command
		argv+=("${group_argv[@]}")
	fi

	# execution phase
	user_command=()
	if [ "$doubledash" -eq 1 ]; then
		user_command=("$@")
	else
		user_command=("${group_argv[@]}")
	fi

	if [ $VERBOSE -eq 1 ]; then echo ">> ARGV: '${argv[*]} -- ${user_command[*]}'"; fi
	execute "${user_command[@]}"
fi