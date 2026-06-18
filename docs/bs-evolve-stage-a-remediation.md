<!-- 交 codex：Stage A 验收 FAIL 后的收口 spec。范围严格限定，勿扩。 -->
# Stage A 收口 spec（codex 重改）

## 背景 / 为什么
Stage A（`docs/bs-evolve-implementation-spec.md` 的「阶段 A」）经独立验收 **FAIL**。**已达标的不要动**：A1①②③（命令体读+导出 config、无项目硬编码、§3.5 四处随迁修正）、A2 的 resume/adopt/git-hygiene、A3（命令注册 + manifest，`verify-manifest.sh` 绿）都是真达标。本 spec 只收 3 个真缺陷 + 流程，**不扩 scope**。

## 铁规则（上一轮出现了两个假测试，这轮明令禁止）
每个验收测试**必须驱动真实代码路径并断言观测到的输出**。以下一律视为不合格、会被打回：
- 硬编码被断言的值（如把 `scheduled_wakeup: False` 当常量写进结果再断言它）。
- 创建产物后不行使就删除（`glob` 到文件→断言存在→`rmtree`，从不 commit/不跑被测逻辑）。
- 断言「文件存在」却不验其必需内容/行为。
- 为「只有活跑才能证」的东西造单元测试假装证明——必须讲清边界、留给活跑，不许伪证。

## 修复项（各一个 commit）

### F1 — init 必须真**提交** fixture（A4②）
缺陷证据：[bs-evolve-init.py:168-171](harness/evolve-loop/bin/bs-evolve-init.py:168) 的 `seed_fixture` 只写盘，注释自承 "committed-**capable**"（=没 commit）；[test_bs_evolve_a4.py:75](tests/test_bs_evolve_a4.py:75) `glob`+`rmtree`，从不 commit、不跑 grade_lint。spec A4② + 设计稿 §5 要的是**提交事务**（否则 Stage 4 私有 worktree 看不到、G2 漏测）。

改：
- `bs-evolve-init.py` 写完 fixture 后，对 **skill 仓** `git add tests/grade_lint_fixtures/<anon-id>/ && git commit`。Stage A 单项目、无并发，**不需要 `SKILL.lock`**（锁是 Stage B 的事，D4）。
- fixture 内容须是真正的 **must-not-fire**：用其 `metadata.yaml` 的 task_type/risk_level 跑 `grade_lint` 必须干净退出。

验收（MUST，可观测、不可造假）：
1. init 后 `git -C <skill> ls-files tests/grade_lint_fixtures/<anon-id>/` 列出 `grade.*` + `metadata.yaml`（证明**已提交**，不只在工作树）。
2. 一个测试：临时 target 上跑 init → 对 skill 仓做**干净 clone 或 `git worktree`** → 在该干净检出上、用 metadata 的 task_type/risk_level 对新 fixture 真跑 `grade_lint` → 断言干净退出。**测试不得删除已提交的 fixture**（它本就该留在仓里）；只清理临时 target 与临时 clone。
3. 匿名断言保留：fixture 无 product 名 / 绝对路径 / decision ID。

### F2 — `--once` 真测试（A1④）
缺陷证据：[bs-evolve-config.py:152,155](harness/evolve-loop/bin/bs-evolve-config.py:152) 的 `once_smoke` 把 `scheduled_wakeup: False` 当常量写进结果——是假断言、且不跑 loop body；[bs-evolve.md:70](commands/bs-evolve.md:70) 还把这个 smoke 模拟器接进了命令体。注意：[bs-evolve.md:58-84](commands/bs-evolve.md:58) 的 `--once` **契约 prose 本身是对的**（推进一步、不 arm wake、不改持久 mode），别动它。

改 + 边界：
- 从命令体与测试中**移除对 `once_smoke` 这个假模拟器的依赖**；删掉硬编码 `scheduled_wakeup` 的断言。
- 命令体 `--once` 分支保持语义：推进一 stage 后**不**执行 Stage-7 `ScheduleWakeup`、且**不**调用任何把持久 `state.mode` 改成 dry-run 的操作。
- 写**真**测试，只断言代码层可观测的部分：在 `mode: auto` 的 state 上、走 `--once` 实际会执行的 state 操作后，`loop-state.py get mode` 仍 == `auto`（证明不污染持久 mode）。
- 「不 arm wake」含 prompt 层、只有活跑能证——**测试里写明这点**，由 Stage A 退出判据的活跑覆盖；**不许**用单元测试伪证。

验收（MUST）：
1. `commands/bs-evolve.md` 的 `--once` 分支文本明确「不 arm Stage-7 wake」「不持久化 mode」，且**不再**通过 `--once-smoke` 模拟器“实现/证明”自己。
2. 真测试：`mode: auto` → 走 `--once` 的真实 state 路径 → `loop-state get mode` 仍 `auto`；**无任何硬编码的 wake 结果断言**。
3. `grep -rn scheduled_wakeup harness/evolve-loop/bin/` 0 命中（或仅在标注 "live-only/prompt-level" 的注释里），且不再有 `--once-smoke` 假子命令被当作验收依据。

### F3 — 守卫扩到任何 reviews 根（A2②）
缺陷：守卫只查 `harness/evolve-loop/reviews/**`。
改：守卫测试断言 skill 仓内**任何路径**下都不存在「项目名/cycle 账本」目录（如 `**/reviews/<project>/`、`**/cycle-NNN/closure.yaml`），不止 `harness/evolve-loop/reviews/`。`bin/*` 仍在且在 manifest 锁内的断言**保留**。

验收（MUST）：构造一个在 skill 仓**别处**（非 `harness/evolve-loop/reviews/`）放下 `reviews/foo/cycle-001/closure.yaml` 的情形 → 守卫测试必须**红**。

## 流程（MUST）
- 在**新分支**（如 `fix/stage-a-acceptance`）上做，F1/F2/F3 **各一个 commit**。
- **不要重写 `main` 历史**——`main` 已 push 到 `origin/main`，原 Stage A 的 commit 留着，本轮只追加修复 commit。
- 全量 `python3 -m unittest discover -s tests -p 'test_*.py'` 仍绿。

## 明确 out-of-scope（别碰、更别造假证）
- **Stage A 退出判据**（OpenSymphony 用 `/loop /bs-evolve` 活跑闭合一个 cycle、行为不掉拍）：这是**活跑**步骤、不是 codex 的交付物，**不准**为它造单元测试。
- `test_grade_lint.py` 读 OpenSymphony 绝对路径的 hermetic 化：属 **B4**，本轮不做。
- 任何 Stage B 机器（`SKILL.lock`、`grade_lint` 规则改动、负向语料 walker、私有 worktree 发版）：不在本轮。

## 返回
列出：改了哪些文件、每条验收的**真实证据**（命令输出 / 测试名）、`unittest` 全量结果（pass 数）。会再过一遍独立验收（同上一轮的对抗式 subagent）。
