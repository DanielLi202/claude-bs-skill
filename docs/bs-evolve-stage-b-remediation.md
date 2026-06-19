<!-- 交 codex：Stage B 独立验收后的收口 spec。范围严格限定。 -->
# Stage B 收口 spec（codex 重改）

## 背景
独立对抗式验收（2 个并发 workflow 部分完成 + 我对 B4/B5/B8 的补充验证，全部**变异测试 + 真跑脚本**）发现 codex 自报的 `PASS_WITH_CAVEATS` **低估了问题**：除 live-only caveat 外，还有 **1 个真 blocker、1 个 hermetic FAIL、2 个真行为 bug/旁路、多处 vacuous 测试**。

**已确认 PASS、不要动**：B1（双锁，证伪通过）、B3（read-ref，证伪通过）、B3b（dedup/no-op，证伪通过）、B7（fleet，证伪通过）。
**行为正确但测试 vacuous（要补测试，别改行为）**：B5 部分、B8。

## 铁规则（codex 反复栽在这——本轮多个脚本从未被任何测试执行）
每个验收测试**必须驱动真实脚本/CLI 并断言观测输出**。禁止：`read_text()`+`assertIn` 源码字符串断言、建产物后即删、仅断言文件存在。
**自检 = 变异测试**：把被测行为破坏掉，对应测试**必须变红**；破坏后仍绿 = vacuous = 打回。本轮 `release.sh` 和 `rollback.sh` 的关键路径**从未被任何测试执行过**（验收时用字符串混淆就绕过了 grep 断言）——必须改成真跑。

## 修复项（各一个 commit）

### F1 — [BLOCKER] release.sh annotated-tag 比较 → 每次真实发版 exit 3（B2）
证据：`release.sh:118` `git tag -a "$VERSION"`（annotated）；`:125` `[ "$(git rev-parse HEAD)" = "$(git rev-parse "$VERSION")" ] || exit 3`。annotated tag 的 `git rev-parse v1.0.1` 返回 **tag-object SHA**（如 7aef175），≠ commit SHA（HEAD）。已对真 bare remote 复现：push 全成功、`merge --ff-only` 成功，但最终比较失败 → **exit 3，每次真实发版都挂**。
改：比较用 peel —`git rev-parse "${VERSION}^{commit}"`（或 `git rev-list -n1 "$VERSION"`）；`:45` anchor 比较若可能收到 VERSION-like ref 也同样 peel。
验收（MUST，行为）：新增集成测试——建 **/tmp bare remote + canonical clone**，满足/桩 G1–G4，真跑 `bash release.sh …`（至少 commit/tag/push/ff/verify 尾段），断言 **exit 0** 且 `origin refs/heads/main` commit == `v$NUM^{commit}` == 本地 HEAD。变异：把 peel 改回裸 `git rev-parse "$VERSION"` → 该测试必须**红**。

### F2 — [BLOCKER] test_grade_lint.py 非 hermetic（B4①）
证据：`tests/test_grade_lint.py:2912,3027` 硬编码读 `/Users/.../OpenSymphony-V3/.prompts/dogfood`，**无 skipUnless**；模拟无 OpenSymphony 跑这 5 个 real-corpus 用例 → `FAILED (failures=2)`（cycle028/cycle029 must-fire 找不到语料而红）。这正是 spec B4 点名要修的文件，B4① 验收（干净机器全绿）不成立。
改：把这些 real-corpus 用例改成 **repo 内 fixture**，或 `@unittest.skipUnless(path.exists(), ...)` 守卫——且 skip 时**不得 vacuous-pass**（"不 fire" 类断言在语料缺失时不能假绿）。
验收（MUST）：模拟无 OpenSymphony（把该路径指向不存在目录 / 临时改 HOME）跑全套 → **全绿（skip，不是 fail，也不是假绿）**。

### F3 — [MAJOR] near-miss 闸门有 `--anchor` 旁路（B4④）
证据：`release.sh:106` 的 near-miss 检查被 `[ -n "$ANCHOR" ]` 包裹。已复现：**不传 `--anchor`** 的 rules-touching 发版、无 near-miss fixture → 全 gate 通过、`DRY` exit 0。spec 要求"触规则但没 near-miss 必须 FAIL"。
改：near-miss 闸门对**任何触 `runtime/grade_lint.py` / 规则 fixture / `tests/test_grade_lint.py` 的发版**无条件强制，**不依赖 `--anchor`**。
验收（MUST，行为）：不传 `--anchor` 的 rules-touching 发版、无 near-miss fixture → 真跑 release.sh → **失败**；加 near-miss fixture → 过。变异确认。

### F4 — [MAJOR] pin-sync abort 路径不原子，留脏树（B6）
证据：`pin-sync.py:72-79` 先 `pin.write_text` + `update_bootstrap_yaml()`，再 `binding.validate`；validate 抛错 → return 4 但**不回滚**已写文件。已复现：malformed `.bootstrap.yaml`（缺 compatible_range）→ exit 4 且 `git status` = ` M .bootstrap.yaml` ` M .bootstrap/contract.sha256`（脏树）。与 B6"committed transaction / 干净树"矛盾——后续 /bs preflight 会因脏树拒绝。
改：validate 失败（及任何 post-write 失败）分支，**先 `git checkout -- <两个文件>` 恢复再 return**。
验收（MUST，行为）：构造 malformed `.bootstrap.yaml` 使 validate 抛错 → pin-sync 非零退出 **且 `git status --porcelain` 为空**（已写文件被回滚）。变异确认。

### F5 — [test-quality] B5 的 G1-anchor 测试 vacuous + G4 case② 缺失（行为正确，只补测试）
证据：`test_bs_evolve_b2_b3.py:76` G1-anchor 测试只 `read_text`+`assertIn`；变异证实——把 G1 的 version-mismatch `sys.exit(1)` 摘掉、保留源码字符串，该测试**仍绿**。另：G4 从未测"无 adjudication file"分支（行为正确，但无断言）。
改：① G1-anchor 改行为测试（真跑 release.sh G1：`contract_version` 匹配但 `version` 不匹配 → 断言非零退出，且变异摘掉 G1 检查后变红）；② 加 G4 case②（无 `--adj-verify` / 无 adjudication file → 拦）的行为测试。

### F6 — [test-quality, FAIL] B8 rollback 测试 vacuous（行为正确，只补测试）
证据：`rollback.sh` 行为经真跑验证全对（lock 持有、只 revert 指名 sha、拒绝歧义 HEAD、保留 pushed tag）。但 `test_bs_evolve_b8.py` 的 ①②④ 只 source-grep；变异证实——注入"删 pushed tag"（字符串混淆 `":refs/""tags"`）或 `reset --hard`+`push --force`（`--h""ard"`）后**全套 B8 测试仍绿**，且 mutant 真的删了 tag / 把共享 main 强推回退、毁掉 sibling 发版。
改：加**行为测试**（真 /tmp bare-remote fixture，origin/main 已越过坏发版）：(a) 真 rollback 后 pushed tag **仍在**；(b) 共享 main **只前进不回绕**（无 force / 无 reset --hard）；(c) SKILL.lock 被占时 rollback **拒绝**（exit 11）。每条都要变异自检（删 tag / force-push 的 mutant 必须使对应测试红）。

## 流程（MUST）
- 新分支（如 `fix/stage-b-acceptance`），**F1–F6 各一 commit**，不重写已 push 的历史。
- 全套 `python3 -m unittest discover -s tests -p 'test_*.py'` 绿 + `verify-manifest.sh` + `grade-fixture-walker.py`。
- **测试只在 /tmp fixture / bare remote 上跑**，绝不碰真 OpenSymphony，绝不 push 任何真 remote，绝不写 skill 仓 git。

## 返回
列出：改了哪些文件、每条验收的**真实证据**（命令输出 / 测试名）、**每条的变异自检结果**（破坏行为→测试红）、`unittest` 全量。我会再独立验收（同样变异测试 + 真跑脚本，重点查 F1/F2 的 blocker 与 F6/F5/F3 的 vacuous 是否真修）。
