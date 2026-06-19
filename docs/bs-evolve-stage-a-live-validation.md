<!-- Stage A 退出判据的活验方案。待人确认后执行。grounded on OpenSymphony 实勘 (2026-06-18)。 -->
# Stage A 活验方案（OpenSymphony）— 待确认

目的：验证 Stage A 退出判据——「OpenSymphony 用 `/loop /bs-evolve` 跑起来，闭合一个完整 cycle（r1→r2→skill_release→remediation→close），行为与迁移前不掉拍」。单元测试已证各部件；只有活跑能证集成不破。

## 0. 实勘到的当前事实（决定了方案形状）

- **loop 静止在干净边界**：`state.json` = `stop_reason: backlog_exhausted`、`iteration 20/max 20`、无 `RUNNING.lock`、`inflight/` 空、无 STOP/PAUSE。→ 满足 §9-A 迁移硬前置，可安全 cutover。
- **OpenSymphony 尚未迁移**：无 `.bs-evolve/`；`.prompts/loop/` 仍是活状态（iter-001..014、reviews、escalations）。→ 活验 = **先 cutover 迁移，再点火**。
- **没有「下一个 cycle」可跑**：backlog 耗尽 + iteration 触顶。
- skill pin 停在 `1.4.19`（state 记录的 skill_sha/version），而 skill 现已 1.4.28+。最新 dogfood cycle = **042**。

## 1. 两个要你先拍板的前置决定

**决定 A — 用什么任务跑验证 cycle？**
backlog 空 + iteration 触顶，直接点火只会立刻 `should-stop` 退出、不跑 cycle。要验证完整 r1→…→close，必须：重置 `stop_reason`、抬 `max_iterations`、**并塞一个真实、低风险、可在 OpenSymphony 一轮内闭合的 backlog 任务**。
- 选项：(a) 我从 OpenSymphony 现状提一个小的真实任务（如一处明确的小修/小测试补全）；(b) 你指定一个；(c) 用一个**无害的合成任务**（纯文档/注释级，确保能闭合但不动产品逻辑）。
- 我的倾向：(c) 合成无害任务——活验要的是「loop 编排不掉拍」，不是「产生有价值的产品改动」；无害任务把变量降到最低、最易判定。

**决定 B — 就地迁移（cutover）由谁建、怎么执行？**
`bs-evolve-init.py` 是给**新**项目的 greenfield 脚手架；OpenSymphony 是**就地**迁移（§9-A.4），其 cutover 步骤目前**无成形脚本**。
- 选项：(a) 给 codex 一份紧的「in-place 迁移脚本」spec，它写 `migrate-inplace.sh`，我验收后执行；(b) 我按 Phase 1 的清单**手动**一次性执行（一次性操作、可快照回滚，省一轮 codex 往返）。
- 我的倾向：(a) 让 codex 写脚本——因为这套迁移将来别的项目也要用，固化成脚本比手动更可复用、可测；且能先在快照上 dry-run。

> 这两个决定定了，我再把下面 Phase 1/3 的占位补成具体命令。

## 2. 分阶段方案（bounded：只验一轮，不开放式跑）

### Phase 0 — 冻结 + 快照（可回滚的地基）
- 再确认静止：`state.json.stop_reason` 非空、无 `RUNNING.lock`、`inflight/` 空、无 armed wake。
- 快照 backup：`.prompts/loop/`、`.prompts/dogfood/`、target 的 reviews、`.bootstrap/`（tar 到仓外），以便任何一步出错可整体回滚。
- 记录迁移前基线：最近一个真实 cycle 的 stage 序列与产物形态（用作 Phase 5 的「不掉拍 = 和它一样」对照）。

### Phase 1 — cutover 迁移（决定 B 落地后补具体命令）
按 §9-A 顺序：① 先把 skill `.gitignore` 落定（已在 main）；② 建 `<os>/.bs-evolve/config.yaml`，**`corpus_dir` 指向现存 `.prompts/dogfood`**（不是空目录）；③ 搬运行态 + reviews 到 `.bs-evolve/`，**reviews/closure 提交进 target 仓**，state/locks/config/corpus gitignore；④ `migrated_through_cycle: 42`（adopt 下界，防重评 018–042）；⑤ 登记 OpenSymphony 进本地 fleet；⑥ **留旧 `.prompts/loop/STOP` 墓碑**吸收任何迟到的旧 wake。

### Phase 2 — 离线完整性校验（点火前，确定性，几分钟）⭐ 最高性价比闸门
不花多小时就能抓住绝大多数迁移错误。全绿才点火：
- `closure.py --reviews-root <os>/.bs-evolve/reviews newest-open` 返回合理（无残留 open closure 误判）。
- adopt 扫描：`migrated_through_cycle=42` 生效，不会去重评 ≤42 的任何 cycle。
- `git -C <os> ls-files .bs-evolve/reviews/**/closure.yaml` 列出账本（**确实 committed**）；`git check-ignore` 命中 state/locks/config/corpus、**不**命中 reviews。
- config 解析：`bs-evolve-config.py --config … --emit-env` 导出全部 `BS_LOOP_*`，路径都落在 target 内。
- `corpus_dir` 下 backtest 能 glob ≥1 code cycle。
- pin/binding：`bs doctor` 或等价校验在迁移后的 target 上不报错（或明确进入 Phase 3 的 pin 刷新）。
- **若 Phase 2 红 → 不点火**，先回退/修迁移（必要时再过 codex），重来。

### Phase 3 — 播种验证 cycle（决定 A 落地）
- 塞入选定的 backlog 任务（pending）。
- `loop-state.py set stop_reason null`；`set max_iterations 21`（只放一轮）；确认 `should-stop` 此刻打印空。
- 刷新 skill pin 到当前 skill（pin 已停在 1.4.19）——用通用 `/bs-refresh-contract` 提交式刷新，使 `/bs` 在干净树 + 新契约上跑（这本身也顺带活验了 §4.8 的 pin 自愈方向）。

### Phase 4 — 点火（bounded 单轮）
- 一行：`/loop /bs-evolve --config <os>/.bs-evolve/config.yaml`（dynamic 无间隔）。
- 因 `max_iterations=21`，闭合一个 cycle 后 Stage 7 不再 re-arm（单轮自停）。
- 预计 2–3h 墙钟。全程不 hold turn（背景 + wake），我在每个 wake 落点核对 Phase 5 清单。

### Phase 5 — 活验观察清单（见 §3）

### Phase 6 — 判定
- **PASS**：一个 cycle 走完 r1→r2→skill_release→remediation→close，产物落在 `<os>/.bs-evolve/reviews/cycle-043/`（**不是** skill 仓），两仓收尾干净，stage 序列与 Phase 0 基线一致。
- **FAIL**：任一「掉拍」信号（§3 右列）。FAIL → 快照回滚 + 定位（多半是迁移或命令体 bug）→ 修 → 重来。

### 中止 / 回滚
- 中止：`touch <os>/.bs-evolve/STOP`（新路径）+ 旧 `.prompts/loop/STOP` 已在（墓碑）。
- 回滚：从 Phase 0 快照整体恢复 `.prompts/loop` / reviews / `.bootstrap`，删 `.bs-evolve/`，target `git reset` 到迁移前。

## 3. 观察清单：不掉拍 vs 掉拍

| 维度 | 不掉拍（PASS 信号） | 掉拍（FAIL 信号） |
|---|---|---|
| Step 0 | guard/closure-scan 正常，正确判定「新 cycle」或 resume | 误判已闭 cycle、重评 ≤42 |
| Stage 1 `/bs` | 子代理跑完一个 cycle、自 commit+merge、产 grade/outcome | `/bs` hard-stop / 卡住 / 找不到任务 |
| Stage 2/3 | r1/r2 产物落 `<os>/.bs-evolve/reviews/cycle-043/` | 产物落进 **skill 仓 reviews**（契约违规） |
| 账本 | `closure.yaml` 依次 r1→r2→skill_release→remediation→closed | closure 卡在某 stage（no-op 哨兵漏写） |
| commit 目标 | review/closure commit 进 **target 仓** | commit 进 skill 仓（§3.5.2 没生效） |
| wake 节奏 | 90/900/2700 档按 stage class 落点 | 无 wake、turn 被 hold、12h 静默 |
| Stage 7 | **先 release 锁、再 arm wake**（§3.5.1） | 锁没释放、下轮 stale 接管 |
| 收尾 | 两仓干净、HEAD 对齐预期 | 残留脏树 / 半发布 / 悬空 tag |

## 4. 范围注记（别误判）

- 这是 **Stage A 单项目** 活验：**不**测并发 / `SKILL.lock` / 私有 worktree 发版 / pin 跨项目传播——那些是 **Stage B**，尚未建。pin 刷新（Phase 3）只用到通用 `/bs-refresh-contract`，是单项目自愈，不是 B 的多项目机制。
- skill 发版（Stage 4）若触发，会真的 tag skill 仓 + 提交一个真实 release。**维护者决定（2026-06-18）：不人为压制——若活验真产出对 bs skill 有价值的进化，应保留并采纳。** 安全靠 gate 自然把关：合成无害任务通常不会产生真实 grade_lint 逃逸 → 无 must-fire → 不会有 spurious 发版;但若真有弱点浮现且通过完整 gate 栈（must-fire backtest + adjudication + fresh-verify + manifest），该 release 就采纳（留在 skill main）。判定时我会把「Stage 4 是否产出 release、是否过 gate、是否采纳」单独列出给你拍板。

---

## 决定（已确认 2026-06-18）
1. **决定 A = (c) 合成无害任务**（纯文档/注释级，确保闭合、不动产品逻辑）。**修正**：不强制 no-op——若活验真产出有价值的 skill 进化且过完整 gate 栈，**采纳保留**（见 §4）。
2. **决定 B = (a) codex 写 `migrate-inplace.sh`**（就地迁移脚本，将来复用 + 可 dry-run）。spec 见 `docs/bs-evolve-inplace-migration-spec.md`。
3. **策略已同意**：bounded 单轮 + Phase 2 离线闸门先绿才点火。

执行顺序：codex 写迁移脚本 → 我独立验收 → Phase 0 快照 → Phase 1 cutover（用脚本）→ Phase 2 离线闸门 → Phase 3 播种（合成任务 + reset latch + pin 刷新）→ Phase 4 点火单轮 → Phase 5/6 观察判定。
