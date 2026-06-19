<!-- 交 codex：写 in-place 迁移脚本。Stage A 退出判据活验的前置。 -->
# bs-evolve in-place 迁移脚本 spec（codex 写 `migrate-inplace.sh`）

## 目标
为一个**已在跑**的项目（OpenSymphony-V3）做 Stage A 就地 cutover：从 legacy `.prompts/loop/` 运行态模型迁到 `.bs-evolve/` config 模型，使其可被 `/bs-evolve --config <path>` 驱动。一次性、**幂等、可回滚、只在静止边界执行**。

## 为什么
`harness/evolve-loop/bin/bs-evolve-init.py` 只覆盖 **greenfield 新项目**。in-place 项目已有运行态（state.json、iter-NNN、escalations、inflight）、dogfood 历史、反复跑过的 loop——需要不同的、**保态**的迁移。这是 Stage A 退出判据活验（`docs/bs-evolve-stage-a-live-validation.md`）的前置。

## 接口（建议；具体 flag 名 codex 可定）
`harness/evolve-loop/bin/migrate-inplace.sh --target <path> --skill <path> --slug <slug> --backup-dir <path> [--dry-run] [--rollback <backup>]`

结构性参考（不是要照抄，是「按这套不变量做」）：设计稿 `docs/bs-evolve-generalization-design.md` §7（config schema）、§9-A（迁移步骤 + 硬前置）、§3.5（随迁修正）、§11 决议。

## 必须做的（结构性，按序）

1. **静止硬前置（fail-closed）**：拒绝执行，除非 target loop 静止——`.prompts/loop/RUNNING.lock` 不存在、`inflight/` 空、无存活 codex 进程组、state.json 已停（`stop_reason` 非空或等价静止信号）。任一不满足 → 非零退出 + 清楚报错，**不动任何文件**。
2. **快照**：迁移前把 `.prompts/loop/`、target 的 reviews、`.bootstrap/` tar 到 `--backup-dir`（供回滚）。`--dry-run`：只做前置检查 + 打印完整计划，**零写**。
3. **建 `.bs-evolve/config.yaml`**（§7 schema）：`corpus_dir` 指向**现存** `.prompts/dogfood`；`migrated_through_cycle` = **自动探测**到的最大 dogfood cycle 号（实勘当前=042，但**不准写死**，要从 `.prompts/dogfood/cycle-*` 探测）；所有路径落在 target 内。
4. **运行态迁移**：state.json 从 `.prompts/loop` 迁到 `.bs-evolve/`，**保留连续性字段**（iteration / mode / anchors / history），修正其中的路径引用。迁移本身**不得**引入新的 stop（旧的 latched `stop_reason` 由活验 Phase 3 显式重置，不是脚本的事；脚本只是别破坏它、也别新增 stop）。
5. **reviews/账本归位**：`reviews/` + closure **提交进 target 仓**。OpenSymphony 的历史评审账本（cycle-018…）此前在 Stage A 已从 **skill 仓删除**、现仅存 skill git history——脚本须从 skill git history **提取归档**进 `<target>/.bs-evolve/reviews/`（committed），使其**不丢、且不在 skill 仓 live tree**。`state/locks/config/corpus/fleet` **gitignore**；`reviews` **不** gitignore。
6. **fleet 登记**：把该项目显式登进**机器本地、gitignored** 的 fleet（§11.2）。
7. **旧 STOP 墓碑**：保留/创建旧 `.prompts/loop/STOP` 吸收任何 armed 的旧 wake（§9-A round-8）。**不删旧 `.prompts/loop` 目录**（留作回滚地基 + 墓碑），直到活验通过。

## 明确不做（out-of-scope；别越界、别造假证）
- 不刷 skill pin（活验 Phase 3 用 `/bs-refresh-contract` 做）。
- 不点火 loop、不塞 backlog 任务、不动 `max_iterations`/`stop_reason`（Phase 3 做）。
- 不碰任何 Stage B 机器（`SKILL.lock`、私有 worktree、pin 跨项目传播）。
- 不删旧 `.prompts/loop`。
- 不对 skill 仓做任何写（只**读** skill git history 取归档）。

## 测试安全（硬约束）
**测试绝不能动真实的 OpenSymphony-V3。** 所有迁移测试在**临时克隆 / fixture target** 上跑（`git clone` 真 target 到 tmp，或构造最小 fixture target）。真实 cutover 只在我验收脚本之后、活验 Phase 1 手动执行。

## 验收（MUST，可观测，禁止假测试）
**铁规则（同前两轮，codex 有前科）**：每个测试必须**驱动真实脚本路径、断言观测到的输出**。禁止：硬编码被断言的值、建产物后即删当证明、仅断言「文件存在」而不验内容/行为、为只有活跑能证的东西伪造单测。

1. **dry-run 零副作用**：`--dry-run` 在一个真 target 的克隆上跑 → 打印完整计划 + 该克隆 `git status` 与 `ls -laR .prompts .bs-evolve` 前后**逐一致**（零文件改动）。
2. **真迁移（在克隆 target 上）后**：
   - `.bs-evolve/config.yaml` 存在；`bs-evolve-config.py --config … --emit-env` 导出全部 `BS_LOOP_*`，路径都在 target 内。
   - `corpus_dir` 解析到现存 dogfood，且 backtest 能 glob ≥1 code cycle。
   - `git -C <clone> ls-files .bs-evolve/reviews` 列出**已提交**的历史账本（证明从 skill history 归档成功）；`git check-ignore` 命中 `state.json`/locks/`config.yaml`/corpus/fleet、**不**命中 `.bs-evolve/reviews/**`。
   - `migrated_through_cycle` == 脚本自动探测到的最大 cycle 号（在 fixture 里放 cycle-007/008/009 → 断言探测出 009，**不是**硬编码 042）。
   - `closure.py --reviews-root <clone>/.bs-evolve/reviews newest-open` 行为合理；adopt 在该下界下不会重评 ≤floor。
   - 旧 `.prompts/loop/STOP` 在；旧 `.prompts/loop` 未删。
3. **静止前置负向测试**：构造一个带 `RUNNING.lock`（或非空 `inflight/`）的 fixture target → 脚本**拒绝执行、非零退出、零文件改动**（断言退出码 + 前后文件一致）。
4. **回滚验证**：迁移 → 用 `--rollback`/`--backup-dir` 恢复 → 该 target 与迁移前**逐文件一致**（含 `.prompts/loop` 内容、无残留 `.bs-evolve`）。

## 流程
- 新分支（如 `feat/inplace-migration`）、**per-item commit**（脚本 1 个 commit、测试 1 个 commit，或合理拆分）。**不重写 main 历史。**
- 全套 `python3 -m unittest discover -s tests -p 'test_*.py'` 仍绿；新迁移脚本若纳入 manifest 锁则同步 relock。

## 返回
列出：改了哪些文件、每条验收的**真实证据**（命令输出 / 测试名）、`unittest` 全量结果。我会用对抗式独立 subagent 再验一遍（重点：dry-run 真零写、自动探测 floor 非硬编码、静止前置真能拒、回滚真能复原、测试没碰真 OpenSymphony）。
