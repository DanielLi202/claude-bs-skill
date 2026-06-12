from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

HELPER = Path(__file__).resolve().parents[1] / 'runtime' / 'reshape_fix_round.py'
sys.path.insert(0, str(HELPER.parent))
from reshape_fix_round import extract_production_loci, fix_round_alignment  # noqa: E402


REAL_CYCLE_021_GRADE = textwrap.dedent('''
# Grade Round 2 — B-021 M7 Evolve Agent (Layer-2) — ESCALATE

Round-2 **REGRESSED** to **3** failing tests (round-0 = 3, round-1 = 2, round-2 = **3**), so the contract's strict-decrease invariant on `grade_summary.p0_count + p1_count` is **violated**. The round-2 fix re-broke `git_commit_footer_records_source_and_off_switch` (passing in round 1) while `commit_required_write_without_commit_fails_closed` (lib.rs:492) and `dogfood_batch_end_to_end` (lib.rs:545) remain failing. The vendor never addressed the actual root cause in production code: `git_write.rs::git_output` still invokes `git` with no locale-independent environment, and `was_candidate_reverted` still matches only English error substrings (`does not have any commits yet` / `your current branch` / `not a git repository`), so under the host's Chinese locale the no-repo / empty-repo `git log` error propagates as `EvolveError::Git` instead of mapping to the empty-repo guard / `EvolveError::CommitRequired`.

Per contract §6 / Step 4: "The agent MUST escalate at Step 4 if ... P0+P1 does not strictly decrease across rounds." Round 1→2 went 2→3. This cycle is **escalated**, not merged. The delta is materially complete and the non-git surfaces all pass (R-AGT-6 isolation, D-P20 split, D-P21 metadata, .evolve.lock, malformed-input, panic audit, L0.5 inline write); the single unresolved defect is the locale-dependent git error classification in `crates/symphony-evolve/src/git_write.rs`. Recommended remediation for a follow-up cycle: force `LC_ALL=C`/`LANG=C` on every `git` `Command` (or branch on git exit status, not localized stderr), and map no-repo to `CommitRequired`.

```yaml
grade_summary:
  p0_count: 0
  p1_count: 3
  p2_count: 0
  adversarial_p0_count: 0
  adversarial_p1_count: 1
```

```yaml
acceptance_status:
  - id: a2
    status: fail
    severity: P1
  - id: a9
    status: fail
    severity: P1
  - id: adv4
    status: fail
    severity: P1
```

## spec_compliance_matrix

```yaml
spec_compliance_matrix:
  - acceptance_id: a5
    evidence_ref: "src/lib.rs dp20_positive_negative_split + dp20_split_rejects (PASS)"
    status: pass
    severity_if_fail: P0
  - acceptance_id: a9
    evidence_ref: "evidence/grade_verify_round_2/cmd_4.stderr.log: git_commit_footer REGRESSED to FAIL in round 2 (lib.rs:478) alongside dogfood_batch (lib.rs:545) — the round-2 fix broke the round-1 init_git repair"
    status: fail
    severity_if_fail: P1
```

## adversarial_checks

```yaml
adversarial_checks:
  - id: adv4
    acceptance_ref: adv4
    status: fail
    severity_if_fail: P1
    evidence_ref: "src/lib.rs commit_required_write_without_commit_fails_closed FAIL. The defect is purely localized-stderr classification: under a non-English git locale was_candidate_reverted() propagates EvolveError::Git instead of the empty-repo/no-repo guard returning Ok(false). Fix: force LC_ALL=C/LANG=C on every git Command or branch on exit status."
```

Single bounded defect — **a2 / a9 / adv4** (and the cascade-skipped tests): make git error handling in `crates/symphony-evolve/src/git_write.rs` locale-independent so `was_candidate_reverted` treats an empty repo / no-repo as `Ok(false)` and the commit-required path returns `EvolveError::CommitRequired` under any locale. Recommended: set `LC_ALL=C` and `LANG=C` (and/or `GIT_*` no-i18n env) on every `git` `Command`, or detect the empty-repo/no-repo condition via `git rev-parse` exit status instead of matching localized stderr substrings. After the fix, `cargo nextest run --workspace` must be fully green.

# Grade Result — B-021 M7 Evolve Agent (Layer-2) — ESCALATED

Unresolved defect: `crates/symphony-evolve/src/git_write.rs` invokes `git` (in `git_output`) without a locale-independent environment, and `was_candidate_reverted` matches only English error substrings.
''')


REAL_CYCLE_022_FRONTEND_GRADE = textwrap.dedent('''
# Grade Round 1 — B-022 Symphony UI — FAIL

The P1 frontend build defect remains unresolved. The production root cause is
not in a helper test: `apps/symphony-ui/package.json` still pins three registry
versions that cannot resolve together, `pnpm-lock.yaml` still records the stale
resolution set, and `src-tauri/icons/icon.png` is still missing as the
compile-time Tauri icon asset. A fix round that only edits `src/foo.test.ts`
does not touch the localized production loci.

```yaml
grade_summary:
  p0_count: 0
  p1_count: 1
  p2_count: 0
```

```yaml
acceptance_status:
  - id: ui-build
    status: fail
    severity: P1
```
''')


def grade(p0=0, p1=1, p2=0, ids=('a2',), body='RAW GRADE PROSE MUST NOT BE INLINED'):
    rows = '\n'.join(f'  - id: {i}\n    status: fail\n    severity: P1' for i in ids)
    return (
        f"# Grade\n"
        f"{body}\n\n"
        f"```yaml\n"
        f"grade_summary:\n"
        f"  p0_count: {p0}\n"
        f"  p1_count: {p1}\n"
        f"  p2_count: {p2}\n"
        f"```\n\n"
        f"```yaml\n"
        f"acceptance_status:\n"
        f"{rows}\n"
        f"```\n"
    )



class ReshapeFixRoundTests(unittest.TestCase):
    def run_helper(self, root: Path, round_number: int, grade_file: str, extra=None):
        cmd = [sys.executable, str(HELPER), '--cycle-dir', str(root), '--outcome-file', str(root / 'outcome.md'), '--grade-file', grade_file, '--round', str(round_number)]
        if extra:
            cmd.extend(extra)
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_happy_path_archives_injects_marker_and_excludes_raw_grade(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'outcome.md').write_text('# Outcome\n', encoding='utf-8')
            (root / 'grade_round_0.md').write_text(grade(p1=2, ids=('a2', 'a4')), encoding='utf-8')
            corrections = root / 'corrections.txt'
            corrections.write_text('- tighten a2\n- add a4 proof', encoding='utf-8')
            proc = self.run_helper(root, 1, 'grade_round_0.md', ['--corrections-file', str(corrections)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((root / 'outcome.v0.md').exists())
            text = (root / 'outcome.md').read_text(encoding='utf-8')
            self.assertIn('bs-fix-round: 1', text)
            self.assertIn('failed=["a2","a4"]', text)
            self.assertIn('Grade detail (reference, not inlined): grade_round_0.md', text)
            self.assertNotIn('RAW GRADE PROSE MUST NOT BE INLINED', text)

    def test_extract_production_loci_from_cycle_021_grade(self):
        loci = extract_production_loci(REAL_CYCLE_021_GRADE)
        self.assertIn('crates/symphony-evolve/src/git_write.rs', loci)
        self.assertNotIn('crates/symphony-evolve/src/lib.rs', loci)
        self.assertTrue(all('/tests/' not in path for path in loci))
        self.assertTrue(all(not Path(path).name.startswith('test_') for path in loci))
        self.assertTrue(all(not Path(path).stem.endswith('_test') for path in loci))

    def test_extract_frontend_manifest_lockfile_and_asset_loci_from_blocking_grade(self):
        loci = extract_production_loci(REAL_CYCLE_022_FRONTEND_GRADE)
        self.assertEqual(
            loci,
            [
                'apps/symphony-ui/package.json',
                'pnpm-lock.yaml',
                'src-tauri/icons/icon.png',
            ],
        )

        aligned, reason = fix_round_alignment(['src/foo.test.ts'], loci)
        self.assertFalse(aligned)
        self.assertIn('apps/symphony-ui/package.json', reason)
        self.assertIn('src/foo.test.ts', reason)

        aligned, _reason = fix_round_alignment(['apps/symphony-ui/package.json'], loci)
        self.assertTrue(aligned)

    def test_production_loci_override_line_is_honored_and_excludes_tests(self):
        text = textwrap.dedent('''
        Production loci: a/b.json, c/d.png, tests/e2e/foo.json, src/foo.test.ts
        P1 blocker remains open in unrelated prose.
        ''')

        self.assertEqual(extract_production_loci(text), ['a/b.json', 'c/d.png'])

    def test_bare_package_json_prose_is_not_extracted(self):
        text = grade(body='P1 root cause says a package.json in general can hide registry drift.')

        self.assertEqual(extract_production_loci(text), [])

    def test_fix_round_alignment_decision_matrix(self):
        loci = extract_production_loci(REAL_CYCLE_021_GRADE)

        aligned, reason = fix_round_alignment(['crates/symphony-evolve/src/lib.rs'], loci)
        self.assertFalse(aligned)
        self.assertIn('crates/symphony-evolve/src/git_write.rs', reason)
        self.assertIn('crates/symphony-evolve/src/lib.rs', reason)

        aligned, _reason = fix_round_alignment(
            ['crates/symphony-evolve/src/lib.rs', 'crates/symphony-evolve/src/git_write.rs'],
            loci,
        )
        self.assertTrue(aligned)

        aligned, reason = fix_round_alignment(['crates/symphony-evolve/src/lib.rs'], loci, alt_justification=True)
        self.assertTrue(aligned)
        self.assertEqual(reason, 'explicit alternate-fix justification')

        aligned, reason = fix_round_alignment(['crates/symphony-evolve/src/lib.rs'], [])
        self.assertTrue(aligned)
        self.assertEqual(reason, 'no production loci extracted (fail-open)')

        aligned, reason = fix_round_alignment([], loci)
        self.assertFalse(aligned)
        self.assertEqual(reason, 'fix round produced no file changes')

    def test_reshape_writes_alignment_sidecar_with_required_loci(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'outcome.md').write_text('# Outcome\n', encoding='utf-8')
            (root / 'grade_round_0.md').write_text(REAL_CYCLE_021_GRADE, encoding='utf-8')
            proc = self.run_helper(root, 1, 'grade_round_0.md')
            self.assertEqual(proc.returncode, 0, proc.stderr)

            sidecar = root / 'fix_round_1_alignment.yaml'
            self.assertTrue(sidecar.exists())
            text = sidecar.read_text(encoding='utf-8')
            self.assertIn('round: 1', text)
            self.assertIn('prior_blocking_count: 3', text)
            self.assertIn('- crates/symphony-evolve/src/git_write.rs', text)
            self.assertIn('alt_justification: false', text)

    def test_resume_safe_noop_when_archive_and_matching_marker_exist(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'outcome.md').write_text('# Outcome\n', encoding='utf-8')
            (root / 'grade_round_0.md').write_text(grade(), encoding='utf-8')
            first = self.run_helper(root, 1, 'grade_round_0.md')
            self.assertEqual(first.returncode, 0, first.stderr)
            before = (root / 'outcome.v0.md').read_text(encoding='utf-8')
            second = self.run_helper(root, 1, 'grade_round_0.md')
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn('no-op', second.stdout)
            self.assertEqual((root / 'outcome.v0.md').read_text(encoding='utf-8'), before)

    def test_second_fix_round_allows_prior_marker_when_blockers_strictly_decrease(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'outcome.md').write_text('# Outcome\n', encoding='utf-8')
            (root / 'grade_round_0.md').write_text(grade(p1=2, ids=('a1', 'a2')), encoding='utf-8')
            (root / 'grade_round_1.md').write_text(grade(p1=1, ids=('a2',)), encoding='utf-8')

            first = self.run_helper(root, 1, 'grade_round_0.md')
            self.assertEqual(first.returncode, 0, first.stderr)
            second = self.run_helper(root, 2, 'grade_round_1.md')
            self.assertEqual(second.returncode, 0, second.stderr)

            self.assertTrue((root / 'outcome.v0.md').exists())
            self.assertTrue((root / 'outcome.v1.md').exists())
            text = (root / 'outcome.md').read_text(encoding='utf-8')
            self.assertIn('bs-fix-round: 1', text)
            self.assertIn('bs-fix-round: 2', text)
            self.assertIn('archive=outcome.v1.md', text)
            self.assertIn('grade=grade_round_1.md', text)
            self.assertNotIn('RAW GRADE PROSE MUST NOT BE INLINED', text)

            before = (root / 'outcome.v1.md').read_text(encoding='utf-8')
            retry = self.run_helper(root, 2, 'grade_round_1.md')
            self.assertEqual(retry.returncode, 0, retry.stderr)
            self.assertIn('no-op', retry.stdout)
            self.assertEqual((root / 'outcome.v1.md').read_text(encoding='utf-8'), before)

    def test_partial_state_is_loud_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'outcome.md').write_text('# Outcome\n', encoding='utf-8')
            (root / 'grade_round_0.md').write_text(grade(), encoding='utf-8')
            (root / 'outcome.v0.md').write_text('# Archived\n', encoding='utf-8')
            proc = self.run_helper(root, 1, 'grade_round_0.md')
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('inconsistent fix-round state', proc.stderr)

    def test_missing_machine_readable_blocks_fail_fast(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'outcome.md').write_text('# Outcome\n', encoding='utf-8')
            (root / 'grade_round_0.md').write_text('# no blocks\n', encoding='utf-8')
            proc = self.run_helper(root, 1, 'grade_round_0.md')
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('grade_summary', proc.stderr)

    def test_bounds_and_strict_decrease_are_enforced(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'outcome.md').write_text('# Outcome\n', encoding='utf-8')
            (root / 'grade_round_0.md').write_text(grade(p1=2, ids=('a1', 'a2')), encoding='utf-8')
            (root / 'grade_round_1.md').write_text(grade(p1=2, ids=('a2', 'a3')), encoding='utf-8')
            too_many = self.run_helper(root, 4, 'grade_round_3.md')
            self.assertNotEqual(too_many.returncode, 0)
            self.assertIn('exceeds max_fix_rounds', too_many.stderr)
            non_decrease = self.run_helper(root, 2, 'grade_round_1.md')
            self.assertNotEqual(non_decrease.returncode, 0)
            self.assertIn('strictly decrease', non_decrease.stderr)

    def test_corrections_cap_enforced(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'outcome.md').write_text('# Outcome\n', encoding='utf-8')
            (root / 'grade_round_0.md').write_text(grade(), encoding='utf-8')
            corrections = root / 'corrections.txt'
            corrections.write_text('x' * 1501, encoding='utf-8')
            proc = self.run_helper(root, 1, 'grade_round_0.md', ['--corrections-file', str(corrections)])
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('corrections exceed', proc.stderr)


if __name__ == '__main__':
    unittest.main()
