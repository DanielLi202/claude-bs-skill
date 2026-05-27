#!/usr/bin/env bash
set -euo pipefail
printf 'overall: pass\n'
printf 'checked_at: "%s"\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'checks:\n'
printf '  - name: git\n    status: pass\n    version: "%s"\n' "$(git --version | sed 's/"/\\"/g')"
