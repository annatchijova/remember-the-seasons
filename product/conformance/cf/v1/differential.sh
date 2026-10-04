#!/usr/bin/env bash
# Differential harness: Python reference verifier vs the clean-room
# Go verifier, over every artifact in this corpus. Both must agree
# on every exit code — same acceptance, same rejection.
#
# usage: ./differential.sh [path-to-mneme-verify]
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="$HERE/../../../verify_cf_offline.py"
GO="${1:-$HERE/../../../verifier-go/mneme-verify}"
[ -x "$GO" ] || (cd "$HERE/../../../verifier-go" && \
    go build -buildvcs=false -o mneme-verify .)
KEYS="$HERE/golden/trusted-keys.json"
fail=0

for f in "$HERE"/golden/canonical.dsse.json \
         "$HERE"/positive/*.dsse.json \
         "$HERE"/mutants/*.json; do
    case "$f" in *expected*) continue;; esac
    python3 "$PY" "$f" "$KEYS" --format=json >/dev/null 2>&1; py=$?
    "$GO" "$f" "$KEYS" >/dev/null 2>&1; go=$?
    if [ "$py" = "$go" ]; then
        echo "AGREE(exit=$py)  $(basename "$f")"
    else
        echo "DIVERGE  $f  py=$py go=$go"; fail=1
    fi
done
exit $fail
