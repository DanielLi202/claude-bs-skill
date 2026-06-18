<!-- design proposal — for human review, not yet implemented -->
# bs-evolve 通用化设计方案（B 路径 · 支持多项目并发自进化）

状态：**草案，待 review** · 作者：evolve-loop maintainer · 目标读者：bs-skill maintainer

---

## 0. 一句话

把现在写死在 `harness/evolve-loop/loop-prompt.md` 里、只能作用于 OpenSymphony-V3 的自进化 loop，**固化成 skill 自带的命令 `/bs-evolve`（算法单源）+ `/bs-evolve-init`（每项目脚手架）**，运行态状态搬到各 target 项目侧，并新增一把 **skill 仓全局锁**，使 N 个项目可以**并发**地各自 dogfood、共享地、串行地把 bs skill 往前进化。

---

## 1. 背景与现状诊断

### 1.1 这个 loop 是什么
`bs-evolve-loop`（closure-ledger 模型）是一个自定速 `/loop`：每个 **closure** = 一次 `/bs` 开发周期 + 包在外面的 6 段进化夹层：

```
r1 独立交付评审 → r2 进程评审找逃逸根因 → skill_release 把规则补进 bs 并发版
→ remediation 用新规则把 target 的遗留也修掉 → close 闭账
```

loop 真正的交付物是 **bs skill 自身的硬化**（新增 `grade_lint` 规则 + 发版）；`/bs` 产出的 dev delta 是「被审计、被挖掘 skill 弱点」的原料，顺带也会被 remediate。已稳定跑过 13 个 cycle（cycle-018 → cycle-030）。

### 1.2 耦合在哪（实测）

| 层 | 耦合度 | 证据 |
|---|---|---|
| `bin/*.py` `*.sh` | **零硬编码**，全部 `--target/--skill/--state-dir/--reviews-root/--corpus-root/--baseline-ref` 参数化 | grep 项目名/绝对路径 = 0 命中 |
| `loop-prompt.md` | **唯一的项目绑定点**，11 处硬编码（绝对路径、`opensymphony` slug、中文 WAKE_PROMPT、codex 账号 gotcha）| 集中在一个文件 |
| `reviews/opensymphony/cycle-NNN/` | **更深耦合**：一个项目的 r1/r2/closure/backtest 证据被 commit 进了 **skill 仓** | 13 个 cycle 目录（cycle-018→030）在 skill 仓里 |
| bs 专属接口 | `grade_lint.py --task-type --risk-level --grade-file --outcome-file --evidence-file --repo-root` + `/bs` cycle 结构 + manifest relock + 版本 pin 点 | backtest.py / release.sh 依赖 |
| 反向耦合 | **无** —— `commands/bs.md` / `contract.md` 不知道 harness 存在 | harness 是 skill 的单向消费者 ✅ |

**结论**：plumbing 已就绪，反向耦合干净。通用化要解决的是 (a) `loop-prompt.md` 的参数化、(b) 状态文件的归属、(c) skill 仓的并发写。

---

## 2. 已定的分歧点（采用推荐）

| # | 决策 | 采用 |
|---|---|---|
| ① | 状态/账本归属 | **搬出 skill 仓 → `<target>/.bs-evolve/`**（config + state + reviews + locks 全在项目侧） |
| ② | 语料 / 跨项目学习 | **must-fire 走 per-project，must-not-fire 走全局**（详见 §5） |
| ③ | skill 仓单写者 | **新增 skill 全局锁，并发本设计的核心**（详见 §4） |
| ④ | 算法 vs 配置 | **算法单源在 skill 命令体；每项目只放 config** |
| ⑤ | 固化形态 | **B 路径：命令 + 脚手架** |

---

## 3. 目标架构（B 路径）

### 3.1 两个命令

| 命令 | 是什么 | 一次调用 = |
|---|---|---|
| `/bs-evolve --config <path>` | 把现在的 `loop-prompt.md` 算法体打包成 skill 命令 | **一个 turn**：Step 0 guard/triage → 从磁盘找到最新未闭合 closure → 推进它**一个 stage**（多数 stage 后台拉起 codex/`/bs` 后立刻结束 turn）→ arm 恰好一个 `ScheduleWakeup` |
| `/bs-evolve-init <target>` | 在一个新项目里铺好 `.bs-evolve/`（config + reviews 目录 + `loop-state.py init` + 种子负向 fixture），并把该项目登记进 skill 侧的 fleet 注册表 | 一次性脚手架 |

`--once`：**瞬态调用标志**（不写 `state.mode`——`loop-state.py init` 只在首次落 mode、之后只有 `set` 才改；若 `--once` 去改持久 mode，会把项目永久卡在 dry-run）。语义 = 本次推进一 stage 后**不 arm wake**、停下，供操作员手动单步/调试。持久 `mode: dry-run` 仍可单独用，但与 `--once` 解耦。

### 3.2 三个时间尺度（消歧「一轮」）

| 概念 | 时长 | 持久化 | `/bs-evolve` 一次调用 |
|---|---|---|---|
| **turn** | 秒~分钟 | 无（除磁盘）| ✅ 就是这个 |
| **closure** | 2-3h | `closure.yaml`（r1→r2→skill_release→remediation→closed）| 跨多 turn |
| **cycle** | 含在 closure | `/bs` step_events | 一个 closure 包一个 cycle |

「跑一轮」= 一个 turn = 推进一个 stage。**故意不能**同步跑完一个 closure —— 硬不变量 0「绝不 hold 住 turn 等外部进程」（cycle-019 的 12h 挂死就是违反它）。

### 3.3 触发机制：`/loop` 是打火机，不是发动机

- **点火**：`/loop /bs-evolve --config <path>`（**dynamic 无间隔**模式）。等价于现状的 `/loop 读取…loop-prompt.md`。
- **链条与节奏**：由命令体自己的 `ScheduleWakeup` 拥有，**不**用 `/loop` 的固定间隔（`/loop 5m` ❌ —— 给不了下面这套 stage-class-aware 的多档 supervision）：

| wake 类型 | delay | 谁 arm | 落在哪 |
|---|---|---|---|
| 下一个 closure（链条）| 90s | Stage 7 | Step 0 全新扫描 |
| 长 stage check-in（/bs、codex、remediation）| 2700s | 后台 stage 后 | Step 0.4 lock-held 裁决 |
| 短 stage check-in（r1-verify、backtest）| 900s | 后台 stage 后 | 同上 |
| lock-held 重试探针 / fallback 心跳 | 1800s / 3600s | 恢复层 | 崩溃恢复 |

### 3.4 再入口机制（比现状更干净）

```
现状  WAKE_PROMPT = "读取 /Users/.../loop-prompt.md 并严格按其执行一轮"   # 手动读文件 + 绝对路径写死
B    WAKE_PROMPT = "/bs-evolve --config /Users/.../<target>/.bs-evolve/config.yaml"  # skill 重入，只剩 config 路径项目相关
```

**自我改进的传播性保持**：skill 命令每次被调用时重读 `commands/bs-evolve.md`，`ScheduleWakeup` 每次重入 `/bs-evolve` → 下一个 wake 自动拿到算法最新版。Stage 4 对 loop 自身算法的自改，变成对 `commands/bs-evolve.md` 的 commit + 随 skill 发版（比现在的未提交文件编辑更可控）。

> **前提（manifest 锁）**：manifest 表里**已列出的** `commands/*` 行受 `verify-manifest.sh` 锁（`contract.md` 的 "Runtime manifest" sha 表，release.sh G3 校验）——**非自动覆盖整个目录**，现表只列了 `commands/bs.md`。`loop-prompt.md` 现在住在 `harness/` 不受锁；搬进 `commands/bs-evolve.md` 后**只有登记进 manifest 表才被锁**——必须把它登记，否则它根本不被校验、「更可控」是空话；登记后，每次自改它的 Stage 4 必须在最后的 version-bump commit 里 relock manifest，否则 G3 红（§4.3 的「manifest relock」标准步已覆盖此，但前提是该文件在表内）。

### 3.5 移植 ≠ 照搬：随迁必须修正的既有点

把 `loop-prompt.md` 搬成 `commands/bs-evolve.md` **不是「算法一字不改」**——以下几处若照搬会出错（codex review 指出），必须随迁修正：

1. **Stage-7 锁释放顺序（既有隐患，照搬即坏）**：现状 Stage 7 把 `loop-guard.sh release`（step 4）放在终止性的 `ScheduleWakeup`（step 3）**之后**——而 ScheduleWakeup 是 terminal、turn 在它那里就结束，于是 release 实际**不执行**，全靠下一 wake 的 stale-lock 接管兜底。搬迁必须改成：**先 close+release 项目锁，再 arm wake 作为最后的终止动作**（Stage 7 拆「闭账/释放」→「arm」，arm 后无任何命令）。
2. **stage 产物的 commit 目标**：现状各 stage 把 r1/r2/closure commit 进 **skill 仓**；搬迁后归 **target 仓**（§9-A.3），每个 `git add/commit/push` 的目标仓要改写。
3. **Stage-5 worktree 命名**：现状 `/private/tmp/remediate-<cycle>` 只带 cycle 号，多项目并发下同号会撞同一路径，必须带 `project_slug` + repo hash（§4.2）。
4. **每 turn 导出 `BS_LOOP_*` 环境**：命令体须在调任何 `bin/` 脚本前从 config 导出（§7 注 2）。

> 所以 §9-A 的「算法逻辑不改」是错措辞——逻辑骨架保留，但以上 4 点是**必须**的随迁修正。

---

## 4. 并发模型（本设计的核心新增）

> **铁律：并发是 inter-project（项目之间），intra-project 仍严格串行。** 单个项目内永远只有一个 in-flight stage；新增的并发只发生在「N 个各自串行的项目 loop，共享一个 bs skill 仓」这一层。

### 4.1 两类资源 → 两把锁

| 资源 | 性质 | 锁 | 谁持有 / 多久 |
|---|---|---|---|
| 单项目的 closure 推进 | 项目私有 | `<target>/.bs-evolve/RUNNING.lock`（现有机制，time-lease 2h）| 该项目 loop，跨整个 turn |
| **任何对 bs skill 仓的写**（Stage 4 实现/回测/发版 **以及 `/bs-evolve-init` 写 fleet.yaml + 种 fixture**）| 全局共享 | **`<skill>/.bs-evolve/SKILL.lock`（新增，原子+token，见下）** | 任一项目 loop 或 init，**持有期 = 该次 skill 写的全程** |

`loop-guard.sh` 的 time-lease 机制是基底，但 **不能原样复用**（这一点最初设计写错了）——它的 `acquire` 是非原子 check-then-act（`[ -e LOCK ]` 测完再 `> LOCK` 写，中间无锁），`release` 是无条件 `rm -f`（无属主校验）。单写者的 per-project `RUNNING.lock` 下这两点是潜伏的；提升成 **真正争用** 的全局锁会被激活：两个 loop 同时见锁空/锁陈旧 → 都 fall through、都写 → 都自认持锁 → §4.3 的「版本号天然唯一」当场崩塌。所以 SKILL.lock 需在 `loop-guard.sh` 之上加三件事（**这是新代码**）：
1. **原子获取**：`mkdir "$LOCK.d"`（存在即失败）或 `set -o noclobber` 写，失败即视为 locked；陈旧回收用 atomic rename-aside，保证只一个赢家。
2. **属主令牌（durable，codex round-10 major）**：acquire 时写一个随机 token 进锁、并 **持久到磁盘**——`closure.yaml.skill_lock: {token, acquired_at, lock_path}`，**不是 agent 上下文记忆**（loop 的 resume 全靠磁盘、跨终止 wake 的 Stage 4 必须能从盘上重读 token）。Step 0.4 加载它、传给每个写/release helper；`release` 只在 token 匹配时才 `rm`（compare-and-delete），挡住「A 陈旧被 B 抢占后 A 苏醒 release 删掉 B 的锁」的双主。持锁时 token 在盘上丢失 = pause-and-surface，不做 best-effort 释放。
3. **租约重校验（硬兜底，codex round-10 minor）**：每次写 skill 仓前、以及 tag/push 前，校验 **token 匹配 + 锁仍新鲜（mtime 未过 stale 阈值）+ 锁 inode/path 仍是当初 acquire 的那个目录/文件**——**不是要求 mtime 相等**（owner 自己心跳 touch 会改 mtime，相等检查会误杀合法 owner）。任一不满足即 abort（fail-closed）。即便续租的「子步 < 2h」软约束被违反、锁被抢占，也不会双写。

> **范围（codex round-2 major）**：SKILL.lock 不止 Stage 4——**任何 skill 仓写都要持它**。`/bs-evolve-init` 写 `fleet.yaml` / 种 `tests/grade_lint_fixtures/<anon-id>/` 也是 skill 仓写；并发 init 不持锁会丢更新 / 交错写，所以 init 的这部分同样在锁内做（或并进首个 Stage 4）。**生效时点**：SKILL.lock 在 Stage B 才落地；Stage A 的单项目自举无并发、不需要它（§9 时序）。
>
> **RUNNING.lock 同样要硬化（codex round-3 major）**：per-project 锁也是 `loop-guard.sh` 的非原子 + 无属主 + 「陈旧即清空接管」机制。隐患：acquire 遇陈旧锁会**静默清空并接管（返回 0）**，绕过 Step 0.4 的 inflight 存活裁决——于是一个 >2h 仍在跑的后台 stage 会被当弃锁、被复制，破坏 SERIAL。修法（与 SKILL.lock 同款）：原子获取 + 属主 token + compare-release；且 **acquire 在「锁陈旧但 inflight 存在」时返回 locked(11)**，强制走 Step 0.4 存活裁决而非静默接管；并在 check-in wake 里续租 RUNNING.lock（不只在 stage 完成后 touch），让活着的长 stage 不过期。

### 4.2 哪些 stage 并发、哪些串行

```
Stage 1 dev (/bs 子代理)          ┐
Stage 2 r1 (codex ro)             │  项目私有 / 重活 / 全部并发
Stage 3 r2 (codex ro)             │  （只受各自 RUNNING.lock 约束）
Stage 5 remediation (worktree)    ┘
─────────────────────────────────────────────────────────
Stage 4 implement+backtest+release  ← skill 仓临界区，SKILL.lock 串行化
```

把唯一的共享可变资源（skill 仓）的写收缩进 Stage 4 的临界区；其余重活（一次 `/bs` 周期 + 2 个评审 + 一个 remediation PR，占了 closure 95% 的墙钟）全程并发。N 个项目同时跑，只在各自到达 Stage 4 的瞬间排队。

**但「写收缩进 Stage 4」不够——读也要隔离（codex blocker）**：r2（Stage 3）读 skill 仓的 contract/runtime/prompts，若此刻另一项目的 Stage 4 正在同一工作树里改文件，r2 会读到半成品；写阶段的 codex 也和别人的读冲突。两条隔离：
- **读者钉提交 ref（codex round-2/9 major：必须钉死，且钉的是「cycle 实际运行时的 skill 版本」）**：r2 是进程评审「当时哪条 gate 该拦却没拦」，所以 Stage 2/3 必须对照 **cycle 运行时生效的规则集**——即该 `/bs` cycle 在 Stage 1 binding 校验时所 pin 的 skill **git ref**——`closure.yaml.skill_read_ref = .bootstrap.yaml.contract.source_commit`（一个真实 git commit/tag），**不是** `.bootstrap/contract.sha256`（codex round-10 major：那是 contract.md 的内容 hash、不是 git ref，`git show <sha256>:path` 解析不出历史树），也**不是** closure-init 时的 `origin/main`（closure 在 cycle 跑完之后才 init，并发下别项目可能已在 Stage 1 期间发版、改了 origin/main——用它会让 r2 评错规则集、把逃逸误判为「已覆盖」）。Stage 2/3 一律 `git show $skill_read_ref:path` 读；`contract_sha256` 仅作单独的完整性字段。与写用的 `anchor.skill_sha`（Stage 4 持锁后 = 当前 origin/main）分开；Stage 5 用刚发布的 tag（pin-sync 之后）。`closure.py init` 现无这些字段，须新增。
- **Stage 4 在私有 worktree 写**：`git worktree add /private/tmp/bs-evolve-skill/<slug>-<cycle> -b skillwork/<slug>-<cycle> origin/main`，per-item commit 落私有分支；**共享 main 只在最后一步**（持锁、fetch、ff/rebase、tag、`push --atomic`）被推进。于是共享工作树永远是干净的已提交态，读者不撞脏树，本地 main 也**永不 ahead**（顺带消除了 §4.5 的 ff-only-on-diverged 问题）。**接线（codex round-4 major）**：`backtest.py --skill-repo` 既当 git 仓又当被测工作树（读 `<skill-repo>/runtime/grade_lint.py`），故 Stage 4 的 backtest 与 `release.sh` 实现侧必须指 **私有 worktree**（候选代码），fetch/tag/锁/`git show` 基线指 **canonical `skill_repo`**。config 因此区分 `skill_repo`（canonical：锁/fetch/tag/基线）与运行时派生的 `skill_worktree`（Stage-4 实现 + `backtest.py --skill-repo` 候选）。

**Stage 5 worktree 也要去全局化**：现状 `/private/tmp/remediate-<cycle>` 只带 cycle 号，不同项目同号会撞；改 `/private/tmp/bs-evolve-remediate/<slug>-<cycle>-<repohash>`，分支同样带 slug。

### 4.3 SKILL.lock 即版本分配器（消除版本撞车）

现在 `release.sh --version vX.Y.Z` 的版本号是 orchestrator 猜的——两个 loop 同时猜 `v1.4.29` 就撞。修法：

1. **基线与版本同源，且 baseline 必须先于 backtest 解析（codex major：原时序把 backtest 排在 alloc-version 前，却需要它输出的 baseline）**。持锁、`git fetch --tags` 后**立即**解析 `baseline = ^v[0-9]+\.[0-9]+\.[0-9]+$` 的语义最大 tag——这步在 backtest 之前。`alloc-version.sh` 之后从**同一锁内 tag 快照**取 `baseline` patch+1 作新版本；临界区内不建新 tag，故 baseline（max）与 version（max+1）天然一致。**从不删已 push 的 release tag（codex round-8 major）**：坏版本走前向 `revert`+patch 发版（§4.6.5），所以 max tag 单调、`max+1` 永无「复用已删版本号」之虞——不需要 burned-version 账本。锁内串行 ⇒ 版本号唯一（不保证连续）。
2. Stage 4 的标准时序（持 `SKILL.lock` 全程；写在私有 worktree，§4.2）：
   ```
   acquire SKILL.lock (原子 + token，§4.1) ──(拿不到则 arm 1800s 重试探针、END)
   git -C $SKILL fetch --tags                               # 看到同伴刚 push 的规则/tag
   anchor.skill_sha = origin/main ；baseline = 语义最大 release tag ；candidate_version = baseline patch+1（不建 tag） # 重锚+基线+候选版本，都在 backtest 前
   worktree add 私有分支 off origin/main（§4.2）
   重核 r2 items vs origin/main（dedup：含同伴已落 + 本 loop 上一 turn 已落，见 4.5）
   per-item 实现 + 每 item commit（落私有分支）+ 每 stage/心跳 touch SKILL.lock（续租，见 3）
   backtest（私有 worktree 当 --skill-repo，§4.2；--baseline-ref = baseline；证据写 backtest/<candidate_version>/）+ adjudicate + fresh-verify
   ──tag/push 前重校验租约 token+mtime；被抢占即 abort（§4.1.3）──
   version = alloc-version.sh（= candidate_version；临界区内无新 tag、故仍 == baseline+1）；版本 bump + manifest relock（私有分支末 commit）
   release.sh（**仅 skill 侧；显式传 canonical 仓 + 候选 ref，不靠 cwd 分支**）：fetch → rebase 私有分支到 origin/main（确保 origin/main 是候选 HEAD 的祖先）→ G1-G4 → tag **候选 HEAD** → `git push --atomic origin <候选HEAD>:refs/heads/main <tag>` → push 后 verify `origin/main == <tag commit>` → **持锁内把 canonical 本地 skill 检出 fast-forward 到该 tag/main（codex round-9 major）**：只推远端会让本地 canonical 的命令文本/契约 hash 停在旧版——下个 wake 读到旧 `commands/bs-evolve.md`、pin-sync 指向本地没有的 hash、Stage 5 canary 跑错规则集；ff 后 verify 本地 `contract.md` hash / `skill.yaml` / 命令文件 / runtime manifest 都 == 发布 tag，才 release SKILL.lock；Stage 5 在这个「已发布的本地/tagged skill」上跑。**绝不**从私有 worktree 跑裸 `git push origin main`（codex round-7 major：现状 release.sh 是 `cd $SKILL` 后 tag HEAD + push main，从 `skillwork/...` 分支会推出「main 不动 + tag 指向私有分支 commit」的坏态，破坏 self-closing/dedup）。（**去掉 reach 进 $TARGET 跑 `scripts/sync-bs-binding.py` 的步骤**——项目专属、新项目没有它会留半个 release；pin 传播改由 §4.8 各 target 自愈）
   release SKILL.lock（token 匹配才删）
   ```
   注：现状 `release.sh` 直接 `git push origin main`、**无 fetch/pull**，且 tag 建在 push 前——故把「push 前 fetch + ff/rebase + `--atomic`」移进 release.sh，tag 只在最后那次 fetch 之后建，非 ff 则重试、不留悬空 tag。
3. **续租**：在 **每个完成的 stage 后** touch（沿用现存 `loop-prompt.md:83` 的 per-stage 规则，**不要降级成 per-commit**——backtest+fresh-verify 这一段无 commit、可达数十分钟无 touch），并对超长子步配墙钟心跳 touch。2h stale 阈值因此意味着「Stage 4 无进展 2h」。**但这是软约束**（LLM 跟 prompt、无看门狗，且语料只增、backtest 墙钟无上界），所以 §4.1.3 的「push 前重校验租约、fail-closed」是真正的硬兜底。
4. **must-fire 只适用于「改 grade_lint code 规则 + target 是 code cycle」（codex round-2 major）**：`backtest.py` 只回放 `cycle.yaml.type == code` 的 cycle，且 must_fire 要求每个 `--target-cycle` 都是其中有 delta error 的；而 `grade_lint` 规则按契约只 scope code 任务。所以 Stage 4 须按改动类型分流：(a) 确定性 r2 项是 grade_lint code 规则 → 走 must-fire backtest；(b) r2 项是非 lint 的确定性改动（contract 条款、runtime guard、driver flag——如真实的 v1.4.22）→ `release.sh --no-backtest "<reason>"`，但 **no-backtest 必须结构化、不能凭任意 reason 放行（codex round-3 major：现状 release.sh 接受任何 reason、不校验 diff，误分类的 grade_lint 规则能借此绕过 must-fire）**：release 须取 base SHA、算改动路径，**仅当 `runtime/grade_lint.py` / grade-lint fixture / backtest 相关测试都未改时**才允许 `--no-backtest`，否则强制 G4；(c) docs/infra/spec/refactor 的 target 闭包通常产不出 code-grade-lint 规则、即无 must-fire 义务。**不能无条件要求 must-fire**。

### 4.4 锁内重锚（stale-anchor 问题）

项目 B 在 Stage 1-3 期间，项目 A 可能已经把 skill 从 v1.4.28 推到了 v1.4.29。所以 B **必须在拿到 SKILL.lock 之后**才确定：
- `anchor.skill_sha` = 当前 HEAD（含 A 的规则）；
- backtest 的 `--baseline-ref` = **此刻**的最新 release tag（v1.4.29），不是 B 启动时的 tag。

否则 B 的 backtest 基线错位、delta 归因失真。

### 4.5 锁内重核 r2 items（避免重复实现同伴已落的规则）

B 的 r2 plan 是在 v1.4.28 规则集下算的。等 B 实现时，A 可能已经为同类逃逸加了规则。Stage 4 持锁后须做一步 **dedup**：逐个 `determinism: deterministic` item 对照当前 HEAD 的规则集，已被覆盖的：
- 从本次实现集剔除；
- 在 `closure.yaml` 把该 item 记为 `covered_upstream: <tag>`（账本保持诚实）。

**所有「无发版」情形都必须写非空哨兵（codex round-4 major：否则 closure.py 卡死在 Stage 4——`skill_release: null` 永远算未完成）**。三种合法无发版，各写明确哨兵 + closure notes：`no-op: covered upstream <tag>`（r2 项全被同伴覆盖）、`no-op: all needs_human escalated`（r2 只产出 needs_human、全进 `escalated_to_human`）、`no-op: no deterministic r2 items`（r2 无确定性项）。置哨兵后 Stage 5 remediation 照常（target 仍需修自己的遗留）。注意 `closure.py` **无需改代码**：`next_stage` 凭「值为真」推进（`skill_release` 平时存的就是个 tag 字符串），哨兵是非空串、天然推进；但 **不能留 null**——null 会被当「未完成」卡住闭合，所以必须写非空哨兵。

**自恢复（resume）走私有分支 + 重新 dedup（codex major：原说「`git pull --ff-only` 不丢本地 commit」在并发下是错的——本地 main ahead + 远端 ahead 时 ff-only 直接失败、dedup 永不运行）**。§4.2 的私有 worktree 模型从根上规避它：per-item commit 落 **私有分支**、**不碰本地 main**，本地 main 永不 ahead、无发散。一个在 Stage 4 中途死掉的 turn 重入时：(1) `git fetch`；(2) 把私有分支 rebase 到最新 `origin/main`（拿同伴已落的规则）；(3) 对照 `origin/main` 重新 dedup，剔除已被覆盖项（含本 loop 上一 turn 已落私有分支、其规则已进 origin 的）；(4) 续做剩余 item。`closure.yaml` 记 `skill_release_items_done: [id…]` 让 resume 不靠纯启发式。dedup 因此既覆盖「同伴已落」也覆盖「自己上一 turn 已落」。

### 4.6 释放/发布模型：直推 + 全局锁（Model A）

每个 loop 在锁内直接 `tag + push` skill 发版（沿用现有 self-closing 不变量「本 iteration 落 main」）。**安全栈**保证一个项目的坏规则不会污染整个 fleet：

1. G4 backtest must-fire + misfire adjudication + fresh-context refute——**但现状 G4 是弱校验（codex major）**：`release.sh` 只查 adj-verify 文件存在、含 `adj_verify` 串、不含字面 `agree: false`；**不**解析 `backtest_adjudication.yaml`、不证明每条 `misfire_candidates[]` 都被裁决。Stage B 须把 G4 改成结构化（§9-B.7b）：解析 report，要求每条 misfire 一条裁决、拒绝任何 `false_positive`、每条裁决有对应 fresh-verify；
2. **G2 全局负向语料**（§5）——对 **已贡献 fixture 的文本** 做回归：新规则若在别项目已贡献的干净片段上误触，G2 红、发版被拦。**这是 best-effort，不是 fleet 全覆盖证明**：残余风险 = (尚未 onboard 的项目) ∪ (已 onboard 项目里未被采样的干净文本)。两条收窄它：(a) 每条 Stage-4 新规则 **必须** 附一个贴边的 near-miss 负向 fixture（init 只种历史干净片段，不覆盖新规则的边界）；(b) onboard 时强制贡献最小负向 fixture 集，未达标不准 `/bs-evolve`；
3. per-item commit ⇒ 坏规则是 `git revert <bad-sha>` + patch 发版，非全量回滚；
4. 同 iteration canary（Stage 5 用刚发的规则 lint 自己的 remediation grade）；
5. **回滚必须锁内 + 指名 sha**：并发下 main 可能已叠了同伴的 v+1，`rollback.sh` 现有的 `git revert HEAD` / `git reset --hard <anchor>` 会误伤同伴发版。回滚前须 **重新 acquire SKILL.lock**，且 `revert <bad-sha>`（绝不在共享 main 上 `reset --hard`）；给 `rollback.sh` 加 `--bad-sha`、HEAD≠该 sha 时拒绝 reset。Stage 5 canary 触发的修复走「前向 patch 发版 vNEXT+1」（重入 Stage 4、再取锁），不走 rollback。**并且 `rollback.sh` 绝不删已 push 的 release tag（codex round-8 major：现状会删 pushed tag → 下个 alloc-version 复用该版本号）——只回退/前向 patch，已 push tag 永久保留，保证 `max+1` 分配无歧义。**

> 备选 **Model B（PR/arbiter）**：每个 loop 开 PR、由单一仲裁者/人串行 merge。更安全但更慢，且打破「本 iteration 落 main」不变量。**当前不采用**，留作 fleet 规模变大或项目不可信时的硬化项。

### 4.7 公平性 / 防惊群

无队列；到达 Stage 4 抢不到 `SKILL.lock` 的 loop arm 一个 wake 后 END。**但必须避免自堵（codex round-5 major）**：该 loop 仍持自己的 `RUNNING.lock`，若只 arm 后 END，下个 wake 它自己的非陈旧 `RUNNING.lock` 会让 Step 0 走 0.4 探针、而非重试 SKILL.lock——直到 `RUNNING.lock` 2h 变陈旧才动。修法：抢锁失败时写一条 `waiting_skill_lock` inflight 记录再 arm wake；Step 0.4 见此记录就**直接重试 SKILL.lock**（拿到→进 Stage 4；仍占→按 `1800 + hash(slug)%600` 抖动重 arm），不等 staleness。少量项目（个位数）够用；几十个再引入显式队列文件。

### 4.8 跨项目 pin 传播（codex round-4 major）

项目 A 发版改了 skill 的 `contract.md` → 所有别项目 `.bootstrap/contract.sha256` 的 pin 立刻过期；`/bs` 的 binding 校验（`lib/binding.py`：`sha256(skill_contract) != locked` 即拒）会让 B/C 的**下一个 `/bs` cycle 直接失败**。所以并发 fleet 必须定 pin 策略。本方案选 **floating-on-latest**：每个项目 loop 在 **Step 0、开新 `/bs` cycle（Stage 1）之前**，检测自己 pin 是否等于当前 skill 契约；过期就先做一次**提交式 pin-sync**（见下）采纳最新，再进 Stage 1。

**pin-sync 必须是提交事务（codex round-6 major）**：现有 `/bs-refresh-contract`（注意是连字符命名，不是 `bs refresh-contract`）只写 `.bootstrap.yaml` + `.bootstrap/contract.sha256`、**默认不 commit**；而 `/bs` 先校验契约、再**拒绝脏树**——只刷文件不提交会让下个 `/bs` 直接挂。所以 `/bs-evolve` 内部 pin-sync 必须：解析最新 reviewed tag/contract sha → 更新 `.bootstrap.yaml` + `.bootstrap/contract.sha256` → 跑 binding 校验 + target verify → **commit + push 一个 target 侧 pin-refresh commit**（让树干净）。这是旧 `scripts/sync-bs-binding.py --commit` 的**通用版**（替换项目专属脚本）；除非 `/bs-refresh-contract` 自己加上文档化的 `--commit` 自动模式，否则由 loop 显式补这个 commit。

- 为什么放 Step 0 而非 release 事务：让 A 的 release 去同步「所有已注册 target」的 pin，会把发版耦合到每个 target 的文件系统状态（可能在别机器/别 in-flight 态），脆弱；各项目在自己边界自愈更稳。
- 时点安全：pin 只在 `/bs` cycle 边界（Stage 1）要紧；Stages 2-5 用 cycle 开始时钉的 `skill_read_ref`（§4.2），不受中途 pin 刷新影响。
- 发版的本项目也一样（codex round-5 major）：release 后、进 Stage 5 remediation 前，对自己的 target 跑上面那个**提交式 pin-sync**（Stage 5 要在新契约下、干净树上验收）——通用步骤，**不**用项目专属的 `scripts/sync-bs-binding.py`（release.sh 已不再 reach 进 target，§4.3）。
- 失败处理：refresh-contract 失败 = pause-and-surface（不静默跳过）。

---

## 5. 语料模型（并发下的跨项目安全）

并发把「per-project 语料利于隔离」与「跨项目防误触需要全局视野」的张力放大。解法是把 backtest 的两半拆开归属：

| | 归属 | 存放 | 作用 | 由谁强制 |
|---|---|---|---|---|
| **must-FIRE** | per-project | **现存的** `<target>/.prompts/dogfood`（含 `cycle.yaml`/`outcome.md`/`grade_round_*.md` 的真实历史 cycle，gitignored、机器本地）—— **不是** 新建空目录 | 证明新规则抓得住本项目的已知逃逸 | Stage 4 backtest（G4 must_fire） |
| **must-NOT-fire** | **全局** | **skill 仓 `tests/grade_lint_fixtures/<anon-id>/`**（各项目干净 cycle 贡献的负向片段，含 negated phrases）| 对已贡献的干净片段做回归（**非** fleet 全覆盖，见 §4.6）| **新增** `tests/test_grade_lint_fixtures.py` walker（进 G2 gate） |

**机制澄清（避免过度承诺）**：`unittest discover -p 'test_*.py'` **不会** 自动跑一个裸 fixture 目录——必须 **新增** `tests/test_grade_lint_fixtures.py`：遍历 `tests/grade_lint_fixtures/<anon-id>/`，每个 fixture 用 sidecar（`meta.yaml: {task_type, risk_level}`）声明参数，断言 `grade_lint` 干净退出，且 **目录空/不可读时 fail-closed**（断言收集到 ≥N 个 fixture，否则测试红——否则「零用例→绿」会在最需要红时放行）。fixture **必须落在 skill 仓内**，G2 才 hermetic、CI 可复现（反例：现状 `tests/test_grade_lint.py` 已有几处硬编码读 `/Users/.../OpenSymphony-V3/.prompts/dogfood` 且 **无 skipUnless 守卫**，换机即 error——别复制这个模式）。所以复用的是 G2 这个 **gate runner**，强制者是新 walker，不是「现有 unittest」。**而且现状那几处硬编码读 OpenSymphony 绝对路径的测试本身就让 G2 非 hermetic（codex major）**：`release.sh` G2 跑整个 suite，换机即 error。所以 Stage B 必须**先把 `tests/test_grade_lint.py` 里读 `/Users/.../OpenSymphony-V3/.prompts/dogfood` 的用例改成 repo 内 fixture（或 skipUnless 守卫）**，否则「skill 可发版」在别机器上根本不成立（§9-B.7）。

`/bs-evolve-init <target>` 落地时：从该项目最近若干干净 cycle 抽取负向片段，**先 sanitize/匿名化（codex round-4 major）**——去掉 product 名、绝对路径、decision ID 等项目身份（contract.md:11 禁止把项目专属内容提交进 skill 仓；grade_lint 是结构/模式匹配、不依赖项目名，匿名后仍驱动规则）——再种进 `tests/grade_lint_fixtures/`（**通用命名空间，不用 `<slug>` 暴露身份**）。**fixture 写入是一个提交事务（codex round-8 major）**：init 在 `SKILL.lock` 内 fetch/rebase/**commit+push 到 origin/main**（不是只写本地未提交文件）——否则 Stage 4 的私有 worktree（off `origin/main`）看不到它们、G2 漏测，或 init 弄脏 canonical 树破坏读隔离。enable 前加检查：候选 worktree 的 G2 确实能看到新 fixture 集。并 **校验 `corpus_dir` 下 backtest 能 glob 到 ≥1 个 code cycle**（否则首个 Stage 4 的 must-fire 永远 false、发版被卡），未通过则 init 不算完成。

**收益**：并发（per-project 语料无争用）+ 跨项目安全（全局负向 fixture，G2 强制），两者兼得。

---

## 6. bs 插件接口（为将来 Option C 留口子，现在不抽象）

loop 对「被进化的 skill」假设了以下接口。文档化但**不**现在抽象——保持 bs 专属，但写清楚，将来要做「skill 无关的元 loop」时照此实现即可：

| 接口 | 现状契约 |
|---|---|
| 确定性 lint | `runtime/grade_lint.py --task-type {code,docs,infra,refactor,spec} --risk-level {low,medium,high} --grade-file --outcome-file [--evidence-file] [--repo-root]`，exit 非 0 = 有 finding（`--evidence-file` CLI 标记可选，但 backtest/release 按约定总是传）|
| dogfood 周期 | `/bs` 自包含跑完一个 cycle，自 commit+merge，产出 grade/outcome/evidence 三件套 |
| 版本 pin 点 | **G1 直接 grep（codex 校正）**：`grep -q "version: \"$NUM\"" skill.yaml` + `contract.md` 中出现 `$VERSION`（**不**查 `contract_version`）。注：该 grep **未锚定**、可能误匹配 `contract_version` 行——release.sh 改造时应锚定（`grep -Eq '^version: "'$NUM'"$'`）或解析 YAML。**G2 间接强制**（`tests/test_binding.py` / `test_codex_driver.py` 断言）：`runtime/preflight.sh` · `runtime/codex_driver.py` · README · bundle 模板。注：`runtime/grade_lint.py` **不** pin skill 版本 |
| 完整性闸门 | `contract.md` 的 "Runtime manifest (locked)" sha 表——`verify-manifest.sh` 只校验**表里已列的** runtime/lib/commands 行（非自动覆盖整个 commands/；现表只列 `commands/bs.md`，故新命令文件须显式加行，§3.4/§3.5） |

---

## 7. Config schema（`<target>/.bs-evolve/config.yaml`）

```yaml
# 由 /bs-evolve-init 生成；每项目一份；算法不在这里，只有参数
schema_version: 1
project_slug: opensymphony            # target 侧 reviews 目录名 / 锁抖动 hash 源。**不**用作 committed fixture 命名空间（那要匿名，§5）；slug→target 映射只存在 gitignored 的本地 fleet/config
skill_repo:  /Users/.../bs-skill      # canonical：锁/fetch/tag/git-show 基线（全局共享）。Stage 4 的实现+backtest 用运行时派生的私有 skill_worktree，不是这个（§4.2）
target_repo: /Users/.../OpenSymphony-V3
state_dir:   /Users/.../OpenSymphony-V3/.bs-evolve     # RUNNING.lock / state.json / STOP / iter-NNN
reviews_dir: /Users/.../OpenSymphony-V3/.bs-evolve/reviews   # ← 搬出 skill 仓（决策①）
corpus_dir:  /Users/.../OpenSymphony-V3/.prompts/dogfood     # per-project must-fire 语料：必须是已含 cycle.yaml/outcome.md/grade_round_*.md 的现存目录，不是新建空目录
mode: auto                            # auto 自链 | dry-run 单步；/bs-evolve-init 须 `loop-state.py init --mode <此值>`（init 不传 --mode 默认 dry-run、永远单步）
migrated_through_cycle: 30            # ← adopt 下界：Step-0 adopt 必须忽略所有 ≤ 此值的 cycle（迁移防回退，§9-A.3）；新项目置 0
max_iterations: 5
fail_threshold: 2
codex:
  reasoning_effort: xhigh
  pass_model_flag: false              # 账号 gotcha：不传 -m，用账号默认
loop_cadence:                         # stage-class-aware wake（§3.3）
  next_closure_sec: 90
  long_checkin_sec: 2700
  short_checkin_sec: 900
  lock_retry_sec: 1800
skill_lock: /Users/.../bs-skill/.bs-evolve/SKILL.lock   # 全局锁路径（所有项目共享同一把）
```

> 注：`reviews_dir` 搬到 target 后，loop 产出的 r1/r2/backtest 证据不再进 skill 仓；skill 仓只接收「skill 改进 commit + 全局负向 fixture」。skill 仓的 `harness/evolve-loop/reviews/opensymphony/` 旧账本 **移出 skill 仓**（含项目身份，contract.md:11；§9-A.3），并加守卫禁止任何项目账本再进 skill 仓。
>
> 注 2：命令体每个 turn 必须先从 config 导出 `BS_LOOP_STATE_DIR/BS_LOOP_SKILL_REPO/BS_LOOP_TARGET_REPO`（沿用现 `loop-prompt.md:42-50` 的 inline 块）再调任何 `bin/` 脚本——否则 `run-codex-staged.sh`（硬要求 `$BS_LOOP_STATE_DIR`）会把 inflight 写错项目。

---

## 8. 目录布局

```
bs-skill/（skill 仓，全局共享）
├── commands/
│   ├── bs-evolve.md              # ← 新增：loop 算法单源（= 现 loop-prompt.md 参数化版）；须加进 contract.md manifest 表才被锁（verify-manifest 只校验已列行）+ 自改时 relock（§3.4）
│   └── bs-evolve-init.md         # ← 新增：脚手架命令（同样登记 manifest + skill.yaml.commands）
├── harness/evolve-loop/bin/      # 随 skill 分发（loop 运行必需）；**纳入 manifest 锁**（扩展 verify-manifest 路径或移到 runtime/evolve-loop/）；加 alloc-version.sh
│   ├── alloc-version.sh          # ← 新增：锁内版本分配
│   └── （loop-guard / loop-state / closure / backtest / release / rollback / verify-manifest / run-codex-staged）
├── tests/grade_lint_fixtures/    # ← 新增：全局负向语料（**匿名 ID 子目录，不用 slug**，§5）
│   └── <anon-id>/…             # 匿名 ID；slug 只存在本地 fleet/config，绝不作 committed fixture 命名空间
├── .bs-evolve/
│   ├── SKILL.lock + SKILL.lock.d/  # ← 新增：skill 全局锁（原子用锁目录）；**整个 .bs-evolve/ gitignored**（§9-A.0）
│   └── fleet.yaml                # ← 新增：项目清单（slug→绝对 target 路径）；**机器本地、gitignored**——项目专属信息，contract.md:11 禁止提交进 skill 仓（§11.2）
└── （harness/evolve-loop/reviews/opensymphony/ 旧账本 **移出 skill 仓** → target/.bs-evolve/reviews 或外部 sidecar，§9-A.3；含项目身份，contract.md:11 禁止留存）

<target>/.bs-evolve/（每项目）
├── config.yaml                  # gitignored（含绝对路径，机器本地）
├── state.json · RUNNING.lock(.d) · STOP · PAUSE · iter-NNN/ · inflight/   # 全部 gitignored（运行态/锁/在途）；只 reviews/ 提交
└── reviews/cycle-NNN/           # ← **提交进 target 仓**（closure 账本是崩溃恢复底座，必须持久；§9-A.3、§11.1）
                                 #   r1 r2 closure.yaml r1_verify remediation_grade backtest/<ver>/
# 注：must-fire 语料用现存的 <target>/.prompts/dogfood（config.corpus_dir 指向它），不在 .bs-evolve 下新建 corpus/（§5/§7）
```

---

## 9. 迁移计划（分步、低风险）

**阶段 A — 不改行为，先解耦（单项目仍可跑）**

> **硬前置（cutover 必须在静止边界）**：迁移 **只在** 满足全部条件时进行——`closure.py newest-open` 返回 exit 10（无 open closure）**且** 无 in-flight stage（`RUNNING.lock` 不存在、`inflight/` 空、无存活的 codex 进程组）**且** 无 armed ScheduleWakeup（loop 已 STOP/latch 停稳）。否则：搬 state 会遗弃活着的进程组 + 旧 wake 携带旧 prompt 字面量重入旧 `loop-prompt.md`（旧路径）→ 双跑、重复 commit。先 `touch STOP` 或确认 `backlog_exhausted`、静止后再动。**并保留旧路径 STOP 墓碑（codex round-8 minor）**：cutover 后**不要立刻删旧 `.prompts/loop` 状态**——ScheduleWakeup 终止且不可取消，已 armed 的旧 wake 仍可能重入旧 prompt；让旧 `.prompts/loop/STOP` 留存吸收这些迟到 wake，直到所有可能的旧 wake 过期（或加一个吸收旧 prompt 重入的 tombstone wrapper）。

0. **先改 skill `.gitignore`（codex round-2/4 major：必须早于任何 `<skill>/.bs-evolve/` 创建）**：忽略 **整个 `<skill>/.bs-evolve/`**——`SKILL.lock`(.d) 与 `fleet.yaml` 都是机器本地态、无要提交的东西（fleet.yaml 含绝对 target 路径 + 项目身份，contract.md:11 禁止进 skill 仓）。整目录忽略也自然覆盖原子锁目录 `SKILL.lock.d/`（解决 round-4 minor）。
1. 抽 `config.yaml`：把硬编码变量化（§7）；`corpus_dir` 指向 **现存的** `.prompts/dogfood`，不是空目录。
2. `loop-prompt.md` → `commands/bs-evolve.md`：开头读 config 并导出 `BS_LOOP_*`，正文用 `$SKILL_REPO/...` 变量。**逻辑骨架保留，但 §3.5 的 4 处随迁修正是必须的**（Stage-7 锁释放顺序、commit 目标改 target 仓、Stage-5 worktree 命名、env 导出）——「一字不改」是错措辞。**登记进 `contract.md` manifest 表并 relock**（否则首个发版 G3 红）。
3. **持久化决策（codex major）**：`reviews/` + closure 账本 **提交进 target 仓**（崩溃恢复底座，必须 committed），只 gitignore `state.json/locks/config/corpus`；各 stage 的 `git add/commit/push` 目标随之从 skill 仓改写到 target 仓（§3.5.2）。运行态迁到 `<target>/.bs-evolve/`（静止前置下）。
   **adopt 防回退（codex blocker）**：新 `reviews_dir` 是空的，adopt 扫描会挑 corpus 里「最新且无 closure 目录者」——单凭 `≥ cycle-018` 一个下界不够稳。须写显式 `migrated_through_cycle: <N>`（或给迁移过的 cycle 落 tombstone closure 记录），adopt 先读这个下界、不碰 ≤N 的 cycle。已 closed 的 13 个 closure **必须移出 skill 仓（codex round-7 major：它们含项目专属路径 + decision/task ID，留存违反 contract.md:11）**：随迁到 target 的 `.bs-evolve/reviews/`（与新账本同处）或外部 sidecar 归档。并加守卫（CI/test）**禁止任何 `reviews/<project>/` 出现在 skill 仓**。**注意只移 `harness/evolve-loop/reviews/**`（项目数据），别误伤 helper（codex round-8 major）**：`harness/evolve-loop/bin/` 是 loop 运行所必需（loop-prompt 用 `$HARNESS/bin/run-codex-staged.sh`、`closure.py` 等），必须随 skill 分发、不能排除——把它们纳入 manifest 锁（扩展 `verify-manifest.sh` 的路径过滤到 `harness/evolve-loop/bin/`，或把 helper 移到 `runtime/evolve-loop/` 落进现有 `runtime/*` 锁域）。
4. 加 `/bs-evolve-init`：铺 `.bs-evolve/` + `loop-state.py init --mode <config.mode>`（不传 `--mode` 默认 dry-run、永远单步）+ 种子负向 fixture + 校验 `corpus_dir` 能 glob ≥1 code cycle + 把 `bs-evolve`/`bs-evolve-init` 加进 **`skill.yaml.commands`**（codex round-2 major：否则命令未注册、不可发现）+ **把 OpenSymphony 登记进 `fleet.yaml`**（in-place 项目须显式登记，否则 fleet-wide STOP 漏掉唯一在跑的项目）。**注（codex round-3 major：解决「先有鸡」）：Stage A 是单项目自举、无并发，这些 skill 仓写不需要锁；从 Stage B（启用并发）起，init 的 `fleet.yaml`/fixture 写才必须持 SKILL.lock——而 SKILL.lock 正是 Stage B.6 才建，二者不冲突。**
- **验收**：OpenSymphony loop 用 `/loop /bs-evolve --config <os>/.bs-evolve/config.yaml` 重启，继续闭合 cycle-031。

**阶段 B — 启用并发（多项目）**
5. （skill `.gitignore` 已在 Stage A.0 改完。）确认 `SKILL.lock` 写路径被忽略，且并发 init / Stage-4 的所有 skill 仓写都在锁内（§4.1 范围）。
6. `SKILL.lock`：**原子获取 + 属主 token + 租约重校验**（§4.1，非「无需新代码」）；`alloc-version.sh`（§4.3，输出 version+baseline）；`release.sh` 改造**严格按 §4.3**：canonical 仓只管 lock/fetch/tag/ref 校验，候选私有 worktree 跑 gate，`git push --atomic <候选HEAD>:refs/heads/main <tag>`，push 后**把本地 canonical fast-forward 到发布 tag**（不是旧的「cwd 跑 `git push origin main`」）。Stage 4 包 acquire/release + 锁内重锚(§4.4) + r2 dedup 含自恢复(§4.5) + per-stage/心跳续租。
6b. **`RUNNING.lock` 也换同款硬化版（codex round-4 major：§4.1 提了但没进迁移计划）**：多项目启动前，把 per-project 锁也改成原子获取 + token + compare-release + 「陈旧但 inflight 在」返回 11 + check-in 续租。
7. 全局负向语料：新增 `tests/test_grade_lint_fixtures.py` walker（**fail-closed on empty**，§5），fixtures 入 repo；每条新规则附 near-miss fixture。**并把现状 `tests/test_grade_lint.py` 里读 OpenSymphony 绝对路径的用例改成 repo 内 fixture / skipUnless**，否则 G2 非 hermetic、换机即红（§5）。
7b. **G4 结构化**：把 `release.sh` G4 从「字符串存在性检查」改成解析 `backtest_adjudication.yaml` + `backtest_report.yaml`：每条 `misfire_candidates[]` 一条裁决、拒绝任何 `false_positive`、每条裁决有对应 fresh-verify（§4.6.1）。**并加 no-backtest 结构化闸门**：`--no-backtest` 只在「改动路径不触 `grade_lint` runtime / 规则 fixture / backtest 测试」时放行，否则强制 G4（§4.3.4）。
7c. **skill 读写隔离**：Stage 2/3 经 `git show <ref>:path` 读钉定 ref；Stage 4 在私有 worktree 写、`push --atomic` 推 main（§4.2）；Stage-5 worktree 改带 `<slug>-<cycle>-<hash>`。
8. `rollback.sh` 改造：`--bad-sha`、锁内执行、拒绝在共享 main 上 `reset --hard`（§4.6.5）。
9. lock-held 重试加 per-project 抖动(§4.7)；`fleet.yaml` 创建语义（init create-if-absent）+ append 串行化（写在锁内）。
- **验收**：第二个项目 `/bs-evolve-init <proj2>` 后并发启动；构造两 loop 同时到 Stage 4，验证版本号不撞（含 token 抢占场景）、commit 不交错、backtest 基线在锁内解析正确、坏规则被 G2 全局语料拦下、空 fixture 目录使测试 fail-closed。

**阶段 C（可选，将来）** —— 抽 bs 插件接口(§6) 成「skill 无关元 loop」（Option C）。本方案不含。

---

## 10. 失败策略与操作员控制（并发版）

- **不变量沿用**：serial（intra-project）· 绝不 hold turn · pause-and-surface 不伪造 · self-closing · per-stage commit。
- **STOP**：`touch <target>/.bs-evolve/STOP` 只停**该项目**。无全局 STOP——逐项目停；要全停就逐个 touch（fleet.yaml 可脚本化）。
- **PAUSE**：`<target>/.bs-evolve/PAUSE` 当前 closure 跑完不再 arm（发版窗口用）。
- **SKILL.lock 卡死**：持锁者死 → 2h time-lease 自动回收（续租保证只在真死时触发）。contested adjudication / escalated 决策仍按现有 pause-and-surface 停在 `closure.yaml`，答在文件里后重启。
- **stop_reason 是 latch**：survives 触发它的条件；重启 checklist 同现状（清 STOP/PAUSE、`set stop_reason null`、确认 `iteration < max`）。

---

## 11. 给 reviewer 的开放问题

1. **`<target>/.bs-evolve/` 的 git 策略**（经 codex review 已**定**，列此备案）：`reviews/` + closure 账本 **提交进 target 仓**（崩溃恢复底座必须 committed），`state.json/locks/config/corpus` gitignore。代价：评审证据进 target 历史。若强烈反对污染 target 历史，替代是提交到一个独立 sidecar 仓——但**绝不能**让账本只存在于未提交的本机文件（否则违反 self-closing 的崩溃恢复前提）。
2. **fleet.yaml**（codex round-4：已改为 **机器本地、gitignored**——含 slug→绝对 target 路径，提交进 skill 仓违反 contract.md:11「不得含项目专属路径/身份」）。残留取舍：若想要跨机可见的注册表，须放 skill 仓外的共享位置（非 skill 仓内提交）。
3. **Model A vs Model B**：直推 + 全局锁是否够安全，还是从一开始就要 PR/arbiter？本方案押 A，但注意安全栈第 2 层（G2 全局负向语料）经 review 已 **降级为 best-effort**（只覆盖已贡献文本，§4.6）——这削弱了「坏规则不污染 fleet」的强度。请在这个更诚实的前提下确认风险偏好。
4. **SKILL.lock 持有时长**：Stage 4 含 implement+backtest 可达 30-60min，期间别的项目阻塞在 Stage 4。是否把 release.sh 拆开、让锁只覆盖 tag+push（更短临界区），还是保持 Stage 4 整体持锁？倾向后者。注：即便超 2h 被抢占，§4.1.3 的「push 前 token 重校验、fail-closed」已是硬兜底，所以这更多是吞吐而非正确性问题。
5. **全局负向语料的增长**：每项目持续贡献 fixture，G2 会越跑越慢。是否需要采样/老化策略，还是规模可控前不管？
6. **单机假设**：当前所有锁/语料/证据都是机器本地（§10）。fleet 是否永远单机？若将来跨机，SKILL.lock 给不了跨机互斥，需换成 remote 推送即真相 + `--atomic`（§4.3 已部分预留），且本方案需要补一节跨机协调。

### 11 决议（按推荐采纳，作为实施约束）

- #1 target git 策略、#2 fleet.yaml 归属：已在 round-4 定（reviews+closure 提交进 target 仓；fleet.yaml 机器本地）。
- **#3 → Model A**（直推 + 全局锁）。fleet 变大/不可信再上 Model B。
- **#4 → 整个 Stage 4 持 SKILL.lock**，不拆 release.sh；正确性靠 §4.1.3 token + fail-closed 重校验兜底。
- **#5 → 暂不做语料老化**；每项目 committed 负向 fixture 限 K 条（最近干净 + 规则边界 near-miss），仅当 G2 墙钟越过预算才引入采样。
- **#6 → v1 显式限定单机**；跨机为独立未来扩展。

> 实施契约见 `docs/bs-evolve-implementation-spec.md`；本文件为其 rationale/参考。

---

## 12. 评审记录（v2 + v3）

本 v2 已折入一轮对抗式自审（5 维度并行评审 → 每条发现独立反驳验证，对照真实 `bin/` 脚本）：**提出 33 条 / 确认 25 条（1 blocker、7 major、10 minor、7 nit）/ 驳回 8 条**。

**已折入的实质修正**：
- **[blocker] 语料迁移**：`corpus_dir` 必须指向现存的 `.prompts/dogfood`（真 must-fire 语料），新建空目录会让首个 Stage 4 的 must-fire 永远 false、发版被卡（§5/§7/§9）。
- **[major] 锁不能原样复用**：`loop-guard.sh` 的 acquire 非原子、release 无属主校验——升为争用全局锁会双主。改为原子获取 + token + 租约重校验（§4.1）。
- **[major] release 推送无防护**：现状 `release.sh` 无 fetch/pull、tag 先于 push。移入 push 前 `pull --ff-only` + `--atomic`（§4.3）。
- **[major] G2 被高估**：全局负向语料只覆盖已贡献文本，非 fleet 全覆盖证明——降级为 best-effort + 两条收窄（§4.6/§5），并据此修正开放问题 #3。
- **[major] G2 非 hermetic / fail-open**：裸 fixture 目录不被 `unittest discover` 跑；需新增 walker，空目录须 fail-closed，fixtures 入 repo（§5）。
- **[major] 迁移会撞活进程**：cutover 须在静止边界（无 open closure / 无 in-flight stage / 无 armed wake）（§9-A 硬前置）。
- **[major] 新命令进 manifest 锁**：`commands/bs-evolve.md` 须登记 manifest 表并 relock，否则「更可控」是空话（§3.4/§8/§9）。
- **[major] 锁/清单未 gitignore**：`.bs-evolve/` 须先写进 skill `.gitignore` 再提交（§8/§9-B）。
- **[minor/nit] 杂项**：cycle 数 30→13；`grade_lint.py` 不 pin 版本（移出 pin 点、补 `preflight.sh`）；`--evidence-file` 实为可选；rollback 须锁内 + 指名 sha；fleet.yaml bootstrap/串行化；alloc-version tag glob + 输出 baseline；Stage-4 自恢复 dedup；哨兵 `skill_release` 无需改 closure.py。

**经验证驳回（不改）**：r2 dedup「lost-update」（设计已在锁内）、self-pin 反馈（不允许 target==skill）、G2 顺序依赖不可复现、per-project must-fire 削弱历史回放、canary 只 lint 自己、取锁 END 丢上下文、no-op 路径 canary 行为——这 8 条要么误读代码、要么被设计已有机制覆盖。

### v3（codex `gpt-5.5` xhigh 深审 round 1 → 已全部折入）

codex 独立深审（read-only，对照真实脚本）判 **FAIL**：2 blocker + 8 major + 3 minor。全部 legitimate，已折入：
- **[blocker] 读未隔离**：Stage 2/3 读共享 skill 工作树会撞见别项目 Stage 4 的半成品 → 读者钉提交 ref + Stage 4 私有 worktree（§4.2）。
- **[blocker] 迁移可能重评已闭 cycle**：空 reviews_dir + adopt 仅靠 `≥cycle-018` 下界 → 加 `migrated_through_cycle` 显式下界（§9-A.3）。
- **[major] 账本持久化未定**：reviews/closure 必须 committed（崩溃恢复底座）→ 提交进 target 仓、改写各 stage commit 目标（§9-A.3、§11.1）。
- **[major] baseline/version 时序自相矛盾**：backtest 排在 alloc-version 前却需要其 baseline → baseline 在 fetch 后、backtest 前解析（§4.3）。
- **[major] self-resume 的 ff-only 在并发下会失败** → 私有分支模型从根上消除发散（§4.5）。
- **[major] G4 是弱字符串校验**，非结构化裁决 → Stage B 改结构化解析（§4.6.1、§9-B.7b）。
- **[major] G2 仍非 hermetic**：现有测试硬编码 OpenSymphony 绝对路径 → 转 repo 内 fixture（§5、§9-B.7）。
- **[major] §8 与 §5/§7 自相矛盾**：§8 仍 scaffold `.bs-evolve/corpus/` → 删除，corpus_dir 指现存 dogfood（§8）。
- **[major] Stage-5 worktree 全局同名**：`/tmp/remediate-<cycle>` 跨项目撞 → 带 `<slug>-<cycle>-<hash>`（§4.2、§3.5.3）。
- **[major] Stage-7 锁释放在终止 wake 之后**（既有隐患，照搬即坏）→ 先 release 再 arm（§3.5.1）。
- **[minor] §6 pin 点 grounding 错**：G1 不查 contract_version；preflight/README 由 G2 强制 → 修正（§6）。
- **[minor] manifest 按行锁非 commands/* 自动**：须显式加行（§3.4/§6）。
- **[minor] `--once` 若改持久 mode 会卡死项目** → 改瞬态标志（§3.1）。

下一轮 codex 复审验证这些修正是否真的成立。

### v3 round 2（codex 复审 → 0 blocker，6 major + 1 minor，已全部折入）

复审确认无 blocker 残留，但指出 round-1 修正多处「方向对、欠落地」+ 新点，已折入：
- **读隔离欠 ref 时点**：`skill_read_sha` 须在 closure init/adopt（Stage 2 前）就钉死、入 closure.yaml，与写用的 `anchor.skill_sha` 分开（§4.2）。
- **migrated_through_cycle 未进 config/Step-0**：补进 §7 config + adopt 须忽略 ≤N（§7、§9-A.3）。
- **init 在锁外写共享 skill 态**：`fleet.yaml`/fixture 写须持 SKILL.lock（§4.1 范围、§9-A.4）。
- **gitignore 时序倒置**：移到 Stage A.0、早于任何 `.bs-evolve/` 创建（§9-A.0、§9-B.5）。
- **skill.yaml 命令注册漏了**：加 `bs-evolve`/`bs-evolve-init` 进 `skill.yaml.commands`（§9-A.4）。
- **非 code 闭包的 must-fire 缺口**：backtest 只回放 code cycle → Stage 4 按是否触 grade_lint 规则分流，非 lint 改动走结构化 `--no-backtest`（§4.3.4）。
- **[minor] init mode**：`loop-state.py init --mode <config.mode>`，`--once` 仅调用级覆盖（§3.1、§7、§9-A.4）。

下一轮 codex 复审验证这些 round-2 修正。

### v3 round 3（codex 复审 → 0 blocker，3 major + 2 minor，已全部折入）

- **迁移时序自相矛盾**：init 在 Stage A.4 要持 SKILL.lock，但锁在 Stage B.6 才建 → Stage A 单项目无并发不需锁，锁要求从 Stage B 起（§9-A.4、§4.1）。
- **RUNNING.lock 也有同款竞态**：非原子 + 陈旧静默接管会复制活着的长 stage、破坏 SERIAL → 同款原子+token+compare-release，且陈旧但 inflight 在时返回 locked、check-in 续租（§4.1）。
- **`--no-backtest` 仍 fail-open**：release.sh 接受任意 reason、不校验 diff → 结构化闸门：只在改动不触 grade_lint runtime/fixture/测试时放行（§4.3.4、§9-B.7b）。
- **[minor] manifest 措辞漂移**：「进 commands/ 即被锁」→「登记进表才被锁」（§3.4、§8）。
- **[minor] gitignore/fleet 不一致**：定为 gitignore 只挡 `SKILL.lock`+`*.tmp`、`fleet.yaml` 提交（§8、§9-A.0、§11.2）。

下一轮 codex 复审验证这些 round-3 修正。

### v3 round 4（codex 复审 → 0 blocker，5 major + 1 minor，已全部折入）

私有 worktree（round-1/2 引入）暴露了更深的接线问题，已折入：
- **私有 worktree 未接 backtest 接口**：`backtest.py --skill-repo` 既是 git 仓又是被测树 → Stage 4 backtest/release 指私有 worktree，canonical `skill_repo` 只管锁/fetch/tag（§4.2、§7）。
- **跨项目 pin 传播缺失**：A 发版改契约 → B/C 的 `.bootstrap` pin 失效、下个 `/bs` 失败 → 新增 §4.8 floating-on-latest（Step 0 自愈 pin）。
- **提交项目专属内容进 skill 仓违反 contract.md:11**：fleet.yaml 改机器本地、fixtures 匿名化入通用命名空间（§5、§8、§11.2）。
- **RUNNING.lock 硬化没进迁移计划** → 补 §9-B.6b。
- **sentinel 只覆盖 covered-upstream**：needs_human-only / 无确定性项也得写哨兵，否则卡死 Stage 4（§4.5）。
- **[minor] gitignore 太窄**：改为忽略整个 skill `.bs-evolve/` + 补全 target 侧 inflight/ 等（§8、§9-A.0）。

下一轮 codex 复审验证这些 round-4 修正。

### v3 round 5（codex 复审 → 0 blocker，3 major + 1 minor，已全部折入）

- **release 仍 reach 进项目专属 `scripts/sync-bs-binding.py`**：新项目没有它 → 半个 release。改 release.sh 仅 skill 侧；pin 由 §4.8 各 target 用通用 `/bs-refresh-contract` 自愈（§4.3、§4.8）。
- **SKILL.lock 抢锁失败会自堵**：持着非陈旧 RUNNING.lock 时下个 wake 走探针而非重试，直到 2h → 写 `waiting_skill_lock` inflight、Step 0.4 直接重试（§4.7）。
- **fixture 匿名化没贯彻**：多处仍 `<slug>` + project_slug 仍当 fixture 命名空间 → 全改 `<anon-id>`、slug 只留本地（§4.1/§5/§7/§8）。
- **[minor] backtest 证据路径需版本号**：`backtest/<ver>/` 但版本在 backtest 后才分配 → backtest 前先算 `candidate_version`（不建 tag）（§4.3）。

下一轮 codex 复审验证这些 round-5 修正。

### v3 round 6（codex 复审 → 0 blocker，1 major + 2 minor，已全部折入）

- **pin-sync 欠落地**：`/bs-refresh-contract`（连字符名）默认不 commit，而 `/bs` 拒脏树 → 定义为提交事务（更新 pin → binding 校验 → commit+push target pin-refresh），修命令名（§4.8）。
- **[minor] §8 仍有 `<slug>` fixture 子目录** → 改 `<anon-id>`（§8）。
- **[minor] §6 G1 grep 未锚定**：`grep "version:"` 可能误匹配 `contract_version` → release.sh 改造时锚定/解析 YAML（§6）。

下一轮 codex 复审验证这些 round-6 修正。

### v3 round 7（codex 复审 → 0 blocker，2 major，已全部折入）

- **私有 worktree 发版可能 tag 不动 main**：裸 `git push origin main` 从 `skillwork/...` 分支会推出「main 不动 + tag 指私有 commit」→ 显式 refspec `HEAD:refs/heads/main` + push 后 verify `origin/main == tag commit`（§4.3）。
- **旧 `reviews/opensymphony` 存档仍违反 contract.md:11**：含项目路径 + decision ID → 移出 skill 仓（迁 target/sidecar）+ 守卫禁止项目账本进 skill 仓 + harness/ 打包排除（§8、§9-A.3、§7）。

下一轮 codex 复审验证这些 round-7 修正。

### v3 round 8（codex 复审 → 0 blocker，3 major + 1 minor，已全部折入）

- **r7 过度修正**：错把整个 harness 排除，但 `bin/` 是 loop 运行必需 → 只移 `reviews/**`，`bin/` 随 skill 分发 + 纳入 manifest 锁（§8、§9-A.3）。
- **fixture 写入未接私有 worktree 模型**：init 写的 fixture 若不 commit+push 到 origin/main，Stage 4 私有 worktree 看不到、G2 漏测 → 定为 SKILL.lock 内的提交事务（§5）。
- **版本「烧掉」只断言未设计**：rollback 删 pushed tag 会让版本号被复用 → 改为「从不删已 push 的 release tag、只前向 patch」（§4.3、§4.6.5）。
- **[minor] 旧 wake 重入**：cutover 后立即删旧 state 会让迟到的旧 wake 重入旧 prompt → 保留旧路径 STOP 墓碑（§9-A）。

下一轮 codex 复审验证这些 round-8 修正。

### v3 round 9（codex 复审 → 0 blocker，2 major + 1 minor + 1 nit，已全部折入）

- **skill_read_sha 钉错时点**：closure 在 cycle 跑完后才 init，钉 origin/main 会评错规则集 → 改钉「cycle 运行时 binding pin 的 contract sha」（§4.2）。
- **私有 worktree 发版只推远端、本地 canonical 没跟上**：下个 wake 读旧命令文本、pin-sync 指向本地没有的 hash、Stage 5 跑错规则 → push 后持锁内 ff 本地 canonical 到发布 tag + verify（§4.3）。
- **[minor] §9-B.6 与 §4.3 矛盾**：仍写「移入 fetch+pull→push main」→ 改为 §4.3 的 refspec + 本地 ff（§9-B.6）。
- **[nit] §12 round-5 记录命令名**：`bs refresh-contract` → `/bs-refresh-contract`（§12）。

下一轮 codex 复审验证这些 round-9 修正。

### v3 round 10（codex 复审 → 0 blocker，2 major + 1 minor，已全部折入）

- **skill_read_sha 用错对象**：`.bootstrap/contract.sha256` 是内容 hash 非 git ref → 改用 `.bootstrap.yaml.contract.source_commit`（真 git ref）当 `skill_read_ref`，sha256 仅作完整性字段（§4.2）。
- **SKILL.lock token 只存 agent 记忆**：违反「resume 全靠磁盘」→ 持久成 `closure.yaml.skill_lock.{token,...}`，Step 0.4 加载（§4.1）。
- **[minor] 租约重校验要求 mtime 相等会误杀 owner 心跳** → 改为 token 匹配 + mtime 未过 stale + inode/path 一致（§4.1.3）。

下一轮 codex 复审验证这些 round-10 修正。

### v3 round 11（codex 复审 → **VERDICT: PASS**，0 blocker / 0 major / 0 minor，仅 1 nit，已修）

- **[nit] §4.8 残留 `skill_read_sha` 术语**（§4.2 已改名 `skill_read_ref`）→ 统一为 `skill_read_ref`。

**收敛**：codex `gpt-5.5` xhigh 深审从 round 1 的「2 blocker + 8 major」一路降到 round 11 的「0/0/0 + 1 nit」并判 PASS。trend：major 数 8→6→3→5→3→1→2→3→2→2→0。设计层面无残留缺陷；剩下的是 §11 的纯方向性人决策。

> 仍待人决策的纯方向性问题集中在 §11（Model A/B 风险偏好、锁时长 vs 吞吐、fleet.yaml 归属、单机假设、语料老化）——这些不是缺陷，是需要你拍板的取舍。
