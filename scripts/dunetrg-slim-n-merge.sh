#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] EOS_PATH

Slim and merge anatree ROOT files from a condor job output directory.

Arguments:
  EOS_PATH              Path to the condor output directory on EOS.

Options:
  -m, --mode MODE       Physics mode passed to dunetrg-io-slim (default: pgun).
  -n, --name NAME       Override the condor job name (default: basename of EOS_PATH).
  -o, --output FILE     Output merged ntuple filename (default: NAME_filtered.ntuple.root).
  -h, --help            Show this help message and exit.
EOF
}

MODE='pgun'
CONDOR_NAME=''
OUTPUT=''

while [[ $# -gt 0 ]]; do
    case "$1" in
        -m|--mode)   MODE="$2";        shift 2 ;;
        -n|--name)   CONDOR_NAME="$2"; shift 2 ;;
        -o|--output) OUTPUT="$2";      shift 2 ;;
        -h|--help)   usage; exit 0 ;;
        -*)          echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
        *)           break ;;
    esac
done

if [[ $# -ne 1 ]]; then
    echo "Error: EOS_PATH is required." >&2
    usage >&2
    exit 1
fi

EOS_PATH="$1"
CONDOR_NAME="${CONDOR_NAME:-$(basename "${EOS_PATH}")}"
OUTPUT="${OUTPUT:-anatree_${CONDOR_NAME}_filtered.ntuple.root}"

ln -sf "${EOS_PATH}" eos

find eos/ -name 'anatree*.root' | tee anatree_"${CONDOR_NAME}".list.txt

uv run dunetrg-io-slim -m "${MODE}" -f anatree_"${CONDOR_NAME}".list.txt
uv run dunetrg-io-merge -o "${OUTPUT}" -m 100 ./data/anatree_*_slimmed_*.root
uv run dunetrg-inspect-trees data/* -q
uv run dunetrg-inspect-trees "${OUTPUT}"
