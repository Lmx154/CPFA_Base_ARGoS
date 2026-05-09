#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
XML_FILE="${ROOT_DIR}/experiments/dcpfa_mvp/DCPFA_visualization_short.xml"
BUILD_IF_NEEDED=1
ARGOS_ARGS=()
HEADLESS=0

usage() {
  printf 'Usage: %s [--headless] [--no-build] [--xml PATH]\n' "$(basename "$0")"
}

while (($#)); do
  case "$1" in
    --headless)
      ARGOS_ARGS+=("-n")
      HEADLESS=1
      shift
      ;;
    --no-build)
      BUILD_IF_NEEDED=0
      shift
      ;;
    --xml)
      XML_FILE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

cd "$ROOT_DIR"

if ((BUILD_IF_NEEDED)); then
  if [[ ! -f build/source/DCPFA/libDCPFA_controller.so || ! -f build/source/DCPFA/libDCPFA_loop_functions.so ]]; then
    cmake -S . -B build -DBUILD_EVOLVER=NO -DCMAKE_BUILD_TYPE=Release
    cmake --build build
  fi
fi

if ((HEADLESS)); then
  TMP_XML="$(mktemp /tmp/dcpfa_visualization_headless.XXXXXX.xml)"
  trap 'rm -f "$TMP_XML"' EXIT
  perl -0pe 's/\n\s*<visualization>.*?<\/visualization>\s*//s' "$XML_FILE" > "$TMP_XML"
  XML_FILE="$TMP_XML"
fi

exec argos3 "${ARGOS_ARGS[@]}" -c "$XML_FILE"
