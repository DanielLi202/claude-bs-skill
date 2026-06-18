<!-- codex 实施契约。rationale/机制依据见 docs/bs-evolve-generalization-design.md（下称「设计稿」）。
     本文件是契约；冲突时以本文件的目标与验收为准，设计稿供查「为什么这么定」。 -->
# bs-evolve 实施规格（codex 交付契约）

## 目标

把 bs skill 的自进化 loop 从「写死在 `harness/evolve-loop/loop-prompt.md`、只作用于 OpenSymphony-V3」固化成 **skill 自带命令**：
- `/bs-evolve --config <path>` — 跑一个 turn（推进最新未闭合 closure 一个 stage）。
- `/bs-evolve-init <target>` — 把任意项目接入自进化。
- `/bs-evolve --once` — 瞬态单步（推进一 stage 后不 arm wake，**不**改持久 `state.mode`），供操作员调试。

并支持 **多项目并发自进化**：N 个项目各自串行地 dogfood bs、共享地、串行地把 bs 往前进化。

完成判据（顶层）：现有 OpenSymphony loop 不掉一拍地迁到新命令继续闭合；再接入第二个项目后,两者可并发跑而不互相破坏 skill 仓。

## 非目标（明确不做）

1. 跨机 fleet — v1 单机（锁/语料/证据都本地）。
2. Model B（PR/arbiter 发布模型）。
3. 抽象成 skill 无关的元 loop（设计稿 Option C / 阶段 C）。
4. 语料老化/采样策略（仅设触发器,不实现）。
5. 重写 `/bs` 自身的 shape/conduct/grade 逻辑——本工作只动 loop 编排与 skill 打包/闸门。

## 锁定的结构性决定（不变量，不要重新讨论）

D1. **算法单源**：loop 算法体只有 skill 里 `commands/bs-evolve.md` 一份；每项目只放 config。自我改进 = 改这个命令体并随 skill 发版。
D2. **状态外置**：运行态与账本归 target 侧 `.bs-evolve/`。`reviews/` + closure 账本**提交进 target 仓**（崩溃恢复底座必须 committed）；锁/state/config/corpus/fleet **gitignored**。skill 仓**不得**含任何项目专属内容（路径、产品名、decision/task ID、项目账本）——这是 `contract.md` 硬边界。
D3. **并发粒度**：并发是 inter-project；单项目内严格串行（永远 ≤1 个 in-flight stage）。
D4. **两把锁**：per-project `RUNNING.lock` + 全局 `SKILL.lock`。两者都必须**原子获取 + 持久化属主 token（落盘，非上下文记忆）+ fail-closed 重校验**。**从 Stage B 起**，任何对 skill 仓的写（Stage 4 发版、init 写 fleet/fixture）都在 `SKILL.lock` 内；**Stage A 单项目自举无并发，不需要 `SKILL.lock`**（但 skill `.gitignore` 必须先于任何 `.bs-evolve/` 创建）。B1 落地后，所有 init/fleet/fixture 的 skill 写都必须持锁。
D5. **私有 worktree 发版**：Stage 4 在 skill 的私有 worktree 写、跑闸门；只在最后一步（持锁）把候选原子推到 skill main+tag,并把**本地 canonical 检出快进到该 tag**。共享工作树任何时刻都是干净的已提交态。
D6. **发布模型 = Model A**：锁内直推 + 全局锁（决议 #3）。坏规则靠安全栈兜底,**从不删已 push 的 release tag**（坏版本走前向 revert+patch）。
D7. **pin 传播 = floating-on-latest**：skill 发版会让别项目的 contract pin 失效;各 target 在自己 Step 0（开新 `/bs` cycle 前）做一次**提交式** pin-sync 自愈,而非由发版方 reach 进所有 target。
D8. **语料两分**：must-fire 用 target 现存的真实 dogfood 语料（per-project）;must-not-fire 用 skill 仓内**匿名化**的全局 fixture,由一个**新增的、空目录即 fail-closed 的** walker 在 G2 强制。
D9. **触发即终止**：每个非终止 turn 以恰好一个 `ScheduleWakeup` 结尾;`/loop /bs-evolve`（dynamic 无间隔）点火,命令体自己的多档 supervision wake 驱动节奏。
D10. **单机假设**（决议 #6）。

> 这些决定的推导、被对抗评审捞出的坑、以及每条对应的真实脚本行,见设计稿 §3–§9、§12。codex 实现时**可以**自行决定字段名、refspec 写法、grep 锚定方式等——设计稿里的此类细节是**参考实现**,不是强制接口;唯一强制的是本节不变量与下面的验收。

---

## 阶段 A — 解耦（单项目仍可跑，零行为差异）

**前置（硬）**：迁移只在静止边界做——无 open closure、无 in-flight stage、无 armed wake;迁移期间保留旧路径 STOP 墓碑吸收迟到的旧 wake。

### A1 — 命令体 + config 抽取
- 目标：`loop-prompt.md` → `commands/bs-evolve.md`,所有项目绑定参数化进 `config.yaml`。逻辑骨架保留,但随迁修正设计稿 §3.5 列的 4 点（Stage-7 先释放锁再 arm、commit 目标改 target 仓、Stage-5 worktree 命名带项目、每 turn 导出环境）。
- 验收（MUST,本项可独立验）：① `commands/bs-evolve.md` 存在,开头读 config 并导出环境;② config 之外无项目硬编码残留;③ 设计稿 §3.5 的 4 处随迁修正都已落（Stage-7 先释放锁再 arm、commit 目标=target 仓、Stage-5 worktree 带项目、每 turn 导出环境）。④ **`--once` 行为**：config `mode: auto` 下跑 `/bs-evolve --once --config <fixture>`，断言恰好推进一个 stage、**不** arm/emit 任何 `ScheduleWakeup`、且 `loop-state.py get mode` 仍是 `auto`（不被改成 dry-run）。整条 loop 的端到端重启见下面「Stage A 退出判据」(需 A1–A4 全到位,故不是本项的独立验收)。

### A2 — 状态/账本迁移
- 目标：运行态 + `reviews/` + closure 迁到 `<target>/.bs-evolve/`;旧 `harness/evolve-loop/reviews/opensymphony/` 移出 skill 仓（迁 target 或外部 sidecar）。`bin/` helper 留在 skill 仓并随之分发（loop 运行必需）。
- 验收（MUST）：① 迁移后从 target 侧账本能正确 resume 一个人为中断的 closure;② 一个 CI/单元测试断言 **skill 仓任何 reviews 根下都不存在项目名/cycle 账本目录**（尤其 `harness/evolve-loop/reviews/**`，不是只看顶层），且 **`harness/evolve-loop/bin/*` 仍随包分发且在 manifest 锁内**（守卫，防回退）;③ adopt 扫描带显式下界,迁移后不重评已闭 cycle;④ **git 卫生（可命令验，防 closure.py 扫到未提交账本而假过）**：`git -C <target> ls-files .bs-evolve/reviews/cycle-*/closure.yaml` 列出账本（确实 committed）;`git check-ignore` 命中 `.bs-evolve/{config.yaml, state.json, RUNNING.lock*, STOP, PAUSE, inflight/**, corpus, fleet 本地态}` 且 **不**命中 `.bs-evolve/reviews/**`;一个全新 clean target checkout 能从 committed 账本 resume。

### A3 — 命令注册 + 完整性闸门
- 目标：`bs-evolve`/`bs-evolve-init` 注册进 `skill.yaml.commands`;新命令文件 + `bin/` helper 纳入 `contract.md` 的 manifest 锁（扩展 `verify-manifest.sh` 覆盖范围,或把 helper 归入已锁域）。
- 验收（MUST）：`/bs doctor` 与 release G3（manifest 校验）在引入新文件后仍绿;改动命令体而不 relock 会让 G3 红（测试为证）。

### A4 — `/bs-evolve-init`
- 目标：一条命令在新项目铺好 `.bs-evolve/`、初始化 state（mode 从 config 透传）、写 target 侧 `.gitignore`、登记本地 fleet、种子匿名负向 fixture。
- 验收（MUST）：在一个干净的第二项目上 init 后：① `corpus_dir` 能 glob 到 ≥1 个 code cycle 否则 init 失败;② **init 实际贡献了新的 committed 匿名负向 fixture**（断言 `tests/grade_lint_fixtures/<anon-id>/` 有新增、带 metadata、无产品名/路径/decision ID），从一个全新 worktree 跑 G2 能看到它们;③ 若产不出最小可匿名化的负向 fixture，init **失败**（不准空贡献）;④ init 不留未忽略的本机态在 skill 仓。

### Stage A 退出判据（聚合，A1–A4 全绿后）
OpenSymphony 用 `/loop /bs-evolve --config <os>` 重启，闭合下一个 cycle 的全流程（r1→r2→skill_release→remediation→close）与迁移前行为一致;config 之外无项目硬编码残留。

---

## 阶段 B — 并发（多项目）

> 前置：阶段 B 任意 skill 仓写之前,skill `.gitignore` 必须已忽略整个 `<skill>/.bs-evolve/`。

### B1 — 两把锁硬化
- 目标：`SKILL.lock` 与 `RUNNING.lock` 都做到原子获取 + 持久化属主 token + fail-closed 重校验 + 「陈旧但仍有 in-flight」返回 locked + 心跳续租。token 持久在盘上（disk-resume 能重读）。
- 验收（MUST）：① 构造两 loop 同时抢 `SKILL.lock`,只有一个进入 Stage 4;② 持锁 turn 被 kill 后,resume turn 能从盘上重读 token 并安全续作或 fail-closed,绝不双写;③ owner 自己的心跳续租不会被重校验误杀;④ 抢锁失败的 loop 不会把自己堵到 2h（用 waiting 态直接重试）;⑤ **stale+inflight 测试**：构造一个过期（mtime 越过 stale 阈值）但仍有 live inflight 记录 / live pgid 的 `RUNNING.lock`，验证 acquire/Step 0 返回 locked、保住 owner 的锁与 token、**不**启动第二个 stage（防 D3 被静默违反）;⑥ **同项目空锁竞争**：对同一项目的空 `RUNNING.lock` 发起两个并发 acquire，恰好一个拿到 owner token 并起一个 in-flight stage，另一个返回 locked/waiting、**不**起 stage（证明 `RUNNING.lock` 同样有原子获取 + compare-release token，不只是 `SKILL.lock`）。

### B2 — 版本分配 + 发版事务（私有 worktree）
- 目标：锁内解析 baseline + 候选版本（均在 backtest 之前,从同一 tag 快照）;实现/回测在私有 worktree;发版用显式候选→main 的原子推 + tag,push 后快进本地 canonical 并校验本地各 pin/manifest == 发布 tag;从不删已 push 的 tag。release.sh 只动 skill 侧,不再 reach 进任何 target。
- 验收（MUST）：① 两 loop 并发发版,版本号不撞、各自 commit 不交错;② 发版后 `origin/main == tag commit` 且本地 canonical == tag;③ **stale-anchor 测试**：项目 A 在 B 等 `SKILL.lock` 期间发版，B 拿锁后的 backtest 证据里 `baseline_ref` == 新的最大 release tag、候选版本 == baseline+1，且都在 backtest 开始**之前**确定;④ 发版后下一个 wake 读到的是新命令体（本地 canonical 已更新）。（回滚见 B8。）

### B3 — 读隔离
- 目标：r2（及任何读 skill 的评审）经钉定的 git ref 读历史树（ref = 该 cycle 运行时的 binding source_commit,不是内容 sha256,不是当前 origin/main）;Stage 4 的写不弄脏共享 canonical 工作树。
- 验收（MUST）：并发下,一个项目长 r2 期间另一个项目发版,r2 仍对照「它那个 cycle 实际运行的规则集」评审（构造测试:两版规则集,验证 r2 用对了那版）。

### B3b — 锁内 r2 dedup + 自恢复 + 无发版闭合
- 目标：Stage 4 拿锁后须**逐个**把确定性 r2 项对照当前 `origin/main` 重核——已被同伴覆盖的剔除并记 `covered_upstream`，只实现未覆盖的（不是照搬现状的「实现全部确定性项」、那会重复同伴已落的规则）；中途死掉的 turn 重入时按 `skill_release_items_done` 重新 dedup、不重复 commit。三种无发版情形（全被同伴覆盖 / 全是 needs_human 升级 / 无确定性项）都必须写**非空哨兵**到 `skill_release`，否则 closure 永远卡在 Stage 4（`next_stage` 只在字段为真时推进）。
- 验收（MUST）：① **部分覆盖**：两个确定性 r2 项，等锁期间同伴发版覆盖了其一 → 拿锁后只发未覆盖的那项、另一项记 `covered_upstream`；② **自恢复**：Stage 4 中途 kill 后重入，不重复 commit 已落项；③ **无发版**：三种 no-op 情形各构造一个，验证写入非空哨兵、`closure.py next` 推进到 remediation/close、closure 能闭合，no-op 情形不发 skill 版本但 remediation 照跑。

### B4 — 全局负向语料 hermetic 化
- 目标：新增遍历 `tests/grade_lint_fixtures/` 的 walker（每 fixture 自带 task_type/risk_level,断言 grade_lint 干净退出,**空/不可读目录即 fail-closed**）;fixture 匿名（无产品名/路径/decision ID,通用命名空间）;把现状 `tests/test_grade_lint.py` 里读 OpenSymphony 绝对路径的用例改成 repo 内 fixture 或 skipUnless 守卫。init 写 fixture 是 `SKILL.lock` 内的提交事务（commit+push 到 main,Stage 4 私有 worktree 才看得到）。
- 验收（MUST）：① 在**没有** OpenSymphony checkout 的干净机器上 `python3 -m unittest discover -s tests` 全绿;② 删空 fixture 目录会让 walker 测试**红**（fail-closed,非 vacuous pass）;③ 一个测试/检查断言 committed fixture 不含产品名/绝对路径/decision ID;④ **每条新规则附 near-miss**：任何触 `grade_lint`/规则的 Stage-4 发版必须新增一个 committed 匿名 near-miss 负向 fixture（私有 worktree 的 G2 看得到）；触规则但没附 near-miss 的发版必须**失败**（init 只种历史干净片段、不覆盖新规则边界，故这条是发版闸,不是 init 职责）。

### B5 — 闸门结构化
- 目标：G4 从字符串存在性检查改成解析回测裁决（每条 misfire 一条裁决、拒绝任何 false_positive、每条裁决有 fresh-verify）;`--no-backtest` 只在「改动不触 grade_lint 规则/fixture/回测测试」时放行,否则强制 G4;G1 版本校验锚定（不误匹配 `contract_version`）。
- 验收（MUST）：四个负向 + 一个正向都生效——① 某 misfire 被裁为 `false_positive` → 拦;② 某 misfire 无对应裁决 → 拦;③ 某裁决无对应 fresh-verify → 拦;④ 「有未裁决 misfire」→ 拦;⑤ 全部 misfire 裁为 true-positive 且各有 fresh-verify → 放行。另：「改动只动 contract 文字、不动规则」可凭结构化 `--no-backtest` 放行，触规则却用 `--no-backtest` 必须被拒。**G1 锚定负向测试**：构造 `contract_version` 匹配但 `skill.yaml` 的 `version` 不匹配的情形，G1 必须 fail（不被 `contract_version` 误匹配放行）。

### B6 — pin 传播
- 目标：实现 D7：各 target 在 Step 0 检测 pin 过期 → 跑通用的**提交式** pin-sync（更新 pin → binding 校验 → commit+push target 一个 pin-refresh commit,使树干净）→ 再开 `/bs`。发版方对自己 target 在 Stage 5 前同样自愈。
- 验收（MUST）：① 项目 A 发版改契约后,项目 B 的下一个 `/bs` cycle 能在干净树上、对齐到新契约地跑起来,不因 binding hash skew 或脏树失败;② **发版方自身**：A 在自己 Stage 5 remediation 之前也跑通用提交式 pin-sync（更新+commit+push 自己 binding、验证干净树 + 新 hash）;③ `release.sh` 不再调用任何项目专属的 target 脚本（如 `scripts/sync-bs-binding.py`）。

### B7 — 操作 + 公平
- 目标：跨项目 STOP（逐项目 + 可脚本化 fan-out 工具,读本地 fleet）;lock-held 重试带 per-project 抖动防惊群;fleet 创建/追加在锁内串行。
- 验收（MUST）：并发 init / fleet 追加在 `SKILL.lock` 内无丢更新;lock-held 重试 delay 含 per-project 抖动。
- 验收（SHOULD）：fleet-wide stop 工具能停到所有在跑项目（含 in-place 迁移的 OpenSymphony,已登记 fleet）。

### B8 — rollback 安全
- 目标：`rollback.sh` 锁内执行、指名 bad sha、拒绝在共享 main 上 `reset --hard` 或回退 `HEAD`（并发下 HEAD 可能是同伴的新发版）、**绝不删已 push 的 tag**。
- 验收（MUST）：构造 `origin/main` 已越过坏发版的场景，rollback 必须持 `SKILL.lock`、拒绝歧义的 HEAD 回退、只 revert 指名的 bad sha、保留所有 pushed tag。

---

## 顶层验收（整套）

1. **迁移不掉拍**：A 完成后 OpenSymphony loop 在新命令上继续自进化。
2. **并发安全**：B 完成后,两项目并发跑,人为让两者同时到达 Stage 4——版本号不撞、commit 不交错、坏规则被语料拦、各自 closure 正常闭合。
3. **契约边界**：守卫测试证明 skill 仓不含任何项目专属内容。
4. **可移植**：在无任何 target checkout 的机器上,skill 的 `unittest` 全绿（hermetic）。

## 交付方式与边界

- 按 work item 交付,每个 item 独立 commit;**先 A 全绿再进 B**。
- 每个 item 完成后我（reasoning 侧）对照本规格的验收逐条核验、跑测试,不接受未验证的「done」。
- 任何与本规格不变量冲突的「更简单做法」,先回报,不要静默偏离。
- 遇到「为什么这么定」的疑问 → 查设计稿对应章节;遇到「这么定对不对」的疑问 → 回报,别自行改不变量。

## 参考

- rationale / 机制 / 被评审捞出的坑：`docs/bs-evolve-generalization-design.md`（§3–§12,含 11 轮 codex 评审记录）。
- 现有 loop 行为基准：`harness/evolve-loop/loop-prompt.md`、`harness/evolve-loop/bin/*`、`harness/evolve-loop/README.md`。

## 评审记录

本 spec 作为「契约」经 4 轮 codex（`gpt-5.5` xhigh，read-only，对照设计稿 + 真实脚本）评审：r1（7 major+1 minor）→ r2（4 major+1 minor）→ r3（3 major）→ **r4 PASS（0 major，2 minor 已折入）**。所有 major 都是「验收没真正测到某不变量」的 false-done 漏洞 + 漏覆盖的设计决定（如锁内 r2 dedup/自恢复、per-rule near-miss fixture、G4 结构化裁决），均已补成可观测验收。底层设计稿独立经 11 轮 codex 评审至 PASS（见设计稿 §12）。
