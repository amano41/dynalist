#!/usr/bin/env bash

set -eu


CMD="$(dirname $(realpath $0))/dynalist-export.py"


function usage() {
	cat 1>&2 <<EOF
Usage: $(basename "$0") <command>

Commands:
    list
    pull
    status
EOF
}


function list() {
	"$CMD" -l
}


function fetch() {

	local id="$1"
	local dest="$(echo "$2" | sed -e 's|^/||').opml"
	local dest_dir=$(dirname $dest)

	if [ ! -d "$dest_dir" ]; then
		mkdir -p "$dest_dir"
	fi

	"$CMD" -e "$id" > "$dest"
}


function pull() {

	if [ ! -f '.dynalist' ]; then
		echo "error: .dynalist not found." 1>&2
		exit 1
	fi

	OLD_IFS="$IFS"
	IFS=$'\t'

	exec < .dynalist
	while read -r id name
	do
		fetch "$id" "$name"
	done

	IFS="$OLD_IFS"
}


function status() {

	if [ ! -f '.dynalist' ]; then
		echo "error: .dynalist not found." 1>&2
		exit 1
	fi

	echo "Files to be downloaded:"

	OLD_IFS="$IFS"
	IFS=$'\t'

	exec < .dynalist
	while read -r id name
	do
		name="$(echo "$name" | sed -e 's|^/||').opml"
		if [ -e "$name" ]; then
			echo -e "\t./$name\t * would be overwritten"
		else
			echo -e "\t./$name"
		fi
	done

	IFS="$OLD_IFS"
}


if [ $# -ne 1 ]; then
	usage
	exit 1
fi

case "$1" in
	"list") list ;;
	"pull") pull ;;
	"status") status ;;
	*)
		usage
		exit 1
		;;
esac
