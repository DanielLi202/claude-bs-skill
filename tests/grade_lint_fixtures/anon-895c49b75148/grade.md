# Anonymous must-not-fire grade fixture
```yaml
grade_summary:
  p0_count: 0
  p1_count: 0
  p2_count: 0
```
```yaml
acceptance_status:
  - id: CFG
    status: pass
    severity: P1
  - id: INIT
    status: pass
    severity: P2
```
```yaml
spec_compliance_matrix:
  - acceptance_id: CFG
    status: pass
    severity_if_fail: P1
    spec_ref: docs/spec.md#config
    evidence_ref: tests/config.rs::locked_dependency_and_yaml_comments
  - acceptance_id: INIT
    status: pass
    severity_if_fail: P2
    spec_ref: docs/spec.md#init
    evidence_ref: tests/init.rs::init_smoke
```
```yaml
negative_regression_tests:
  - acceptance_id: CFG
    status: pass
    severity_if_fail: P1
    scenario: malformed secret-bearing YAML does not echo the secret and locked dependency is present
    evidence_ref: tests/config.rs::malformed_secret_yaml_is_redacted
```
```yaml
secret_leakage_audit:
  status: pass
  checked_surfaces: [debug, display, errors, logs]
  cleartext_secret_probe:
    status: pass
    shapes:
      - token=sk-secret-test
      - '{"api_key":"sk-secret-test"}'
      - "Authorization: Bearer sk-secret-test"
  evidence_ref: tests/config.rs::malformed_secret_yaml_is_redacted
```
```yaml
dependency_spec_review:
  - dependency: serde_yaml_bw
    status: pass
    severity_if_fail: P1
    spec_ref: docs/architecture/tech-stack.yaml
    evidence_ref: cargo tree -p generic-config
```
