---
schema_version: "1.1"
id: "TASK_REDACTED"
iteration: 1
previous_iteration_id: null
title: "verify-docs.sh Check 10: deprecated register ID reference detection"
goal: "Add Check 10 to scripts/verify-docs.sh that warns when docs reference a register ID marked deprecated/superseded in its owner register without a local deprecated annotation"
non_goals:
  - "Do not change behavior of Check 0-9"
  - "Do not modify any register file or add/remove deprecated IDs"
  - "Do not add enforcement to ci-docs.sh — this check lives in verify-docs.sh only"
  - "Do not attempt to auto-fix deprecated references — warn only"
context_pointers:
  - "scripts/verify-docs.sh"
  - "docs/JUDGMENT_REDACTED/architecture.md"
  - "docs/JUDGMENT_REDACTED/product.md"
  - "docs/JUDGMENT_REDACTED/ux.md"
  - "docs/ops/risks.md"
  - "docs/ops/contributing.md"
  - "AGENTS.md"
mode: relaxed
risk_level: low
high_risk_actions: []
tags:
  - dogfood
acceptance:
  - id: a1
    text: "Check 10 runs without error on current repo (no false positives)"
    type: command
    command: "bash scripts/verify-docs.sh 2>&1 | grep -q 'verify-docs OK'"
    timeout_sec: 120
    required_exit_code: 0
  - id: a2
    text: "Injecting a bare deprecated-ID reference triggers a Check 10 warning"
    type: command
    command: |
      set -e
      TMPFILE=$(mktemp ABS_PATH_REDACTED
      trap 'rm -f "$TMPFILE"' EXIT
      # Create a test file that references ~~TASK_REDACTED~~ (deprecated) without annotation
      mkdir -p docs/_test_check10
      echo "This doc references TASK_REDACTED as if it were active." > docs/_test_check10/fake.md
      # Run verify-docs and capture output
      output=$(bash scripts/verify-docs.sh 2>&1 || true)
      rm -rf docs/_test_check10
      # The output must mention Check 10 or deprecated reference warning for TASK_REDACTED
      echo "$output" | grep -qi "deprecated.*TASK_REDACTED\|TASK_REDACTED.*deprecated\|Check 10"
    timeout_sec: 120
    required_exit_code: 0
  - id: a3
    text: "A reference with local deprecated/superseded/strikethrough annotation does NOT trigger warning"
    type: command
    command: |
      set -e
      mkdir -p docs/_test_check10
      # Reference TASK_REDACTED but with proper deprecated context annotation
      echo "~~TASK_REDACTED~~ was reversed; see TASK_REDACTED' for current JUDGMENT_REDACTED" > docs/_test_check10/annotated.md
      output=$(bash scripts/verify-docs.sh 2>&1 || true)
      rm -rf docs/_test_check10
      # Must NOT contain a Check 10 warning for TASK_REDACTED from annotated.md
      if echo "$output" | grep -q "_test_check10/annotated.md.*TASK_REDACTED"; then
        echo "FAIL: false positive on properly annotated deprecated reference"
        exit 1
      fi
      echo "PASS: annotated reference correctly excluded"
    timeout_sec: 120
    required_exit_code: 0
  - id: a4
    text: "Check 10 detects superseded TASK_REDACTED references without annotation"
    type: command
    command: |
      set -e
      mkdir -p docs/_test_check10
      echo "The Grade UI follows TASK_REDACTED for sanity check behavior." > docs/_test_check10/fake-ux.md
      output=$(bash scripts/verify-docs.sh 2>&1 || true)
      rm -rf docs/_test_check10
      echo "$output" | grep -qi "TASK_REDACTED.*deprecated\|TASK_REDACTED.*superseded\|deprecated.*TASK_REDACTED"
    timeout_sec: 120
    required_exit_code: 0
  - id: a5
    text: "Existing checks 0-9 pass unchanged (regression guard)"
    type: command
    command: "bash scripts/verify-docs.sh"
    timeout_sec: 120
    required_exit_code: 0
  - id: a6
    text: "Check 10 correctly skips owner register files themselves"
    type: artifact
    artifact_path: "scripts/verify-docs.sh"
    must_exist: true
    must_contain:
      - "Check 10"
    must_not_contain:
      - "Check 11"
output_contract:
  artifacts:
    - type: file_set
      paths:
        - "scripts/verify-docs.sh"
  target: pr
verification:
  mode: agent-driven
  required_evidence:
    - run_logs
    - git_diff
    - t
