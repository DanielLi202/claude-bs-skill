<!-- 交 codex：/bs-evolve 零参 UX(从目标项目根直接跑)。范围严格限定。 -->
# bs-evolve 零参 UX spec（codex 实施）

## 目标
让核心调用路径**不再出现 `--config`**：
- **已初始化的项目**（目标仓里有 `.bs-evolve/config.yaml`）：在该仓内 `/loop /bs-evolve`（无 `--config`）**直接跑**。
- **未初始化的项目**：`/bs-evolve`（无 `--config`）**fail-closed**，打印明确提示「先跑一次 `/bs-evolve-init`」，**不**自动推导、**不**擅自把当前仓当目标进化。
- `--config <path>` 保留为**高级覆盖**（非标准布局 / 一个 checkout 多项目），从核心文档路径降级，不再是必填。

## 已就位、不要动
- `/bs-evolve-init` 已默认 `--mode auto` 并写出 `config.yaml`（schema_version/project_slug/state_dir/reviews_root/corpus_dir/mode）。→ 「初始化后连续跑」已成立,本轮不改 init 的约定/mode。
- `bs-evolve-config.py` 的 `wake_prompt` 已烧入**解析后的绝对 config 路径**。→ 自链 wake 跨 turn 不依赖 CWD,已正确,本轮保持。

## 行为契约（discovery）
`bs-evolve-config.py`（被命令体调用）解析顺序：
1. 给了 `--config <path>` → 用它（现状,完全覆盖,不变）。
2. 没给 `--config` → **发现**：`target = git -C <CWD> rev-parse --show-toplevel`（进程 CWD 的 git 根——用户在目标仓内运行时即目标仓；命令体在调用前不得 cd 走）；config = `<target>/.bs-evolve/config.yaml`。
   - 文件存在 → 加载并继续（mode 取自 config；init 写的是 auto,故已初始化项目连续跑）。`wake_prompt` 仍烧入这个**解析后的绝对路径**（人敲零参,内部自链用绝对 `--config`）。
   - 文件不存在 → **非零退出 + 可执行提示**：例如 `bs-evolve: <target> 未初始化（无 .bs-evolve/config.yaml）；先运行一次 /bs-evolve-init`。**不** emit-env、**不**推导、**不**进任何 stage。
   - CWD 不在 git 仓内 → 明确非零错误（不是 traceback）。

## 改动范围
- `harness/evolve-loop/bin/bs-evolve-config.py`：`--config` 改为**可选**；无则按上面发现 git 根的 `.bs-evolve/config.yaml`；缺失给 actionable 错误（指向 `/bs-evolve-init`）；保留 wake_prompt 烧绝对路径。
- `commands/bs-evolve.md`：核心调用文档改成**零参** `/loop /bs-evolve`（在目标仓内）；`--config` 移到「高级覆盖」小节;写明未初始化的报错与 `/bs-evolve-init` 指引。
- 二者均在 manifest 锁内 → **relock**;并随**版本号 bump**（建议 1.5.1 patch:additive UX,无破坏；`/bs` 契约不变）落地——否则又出现 contract 改了但版本没动的偏移（v1.5.0 的教训）。

## 验收（MUST,行为 + 变异自检；codex 反复栽在 vacuous 测试）
铁规则:每条都**驱动真实 `bs-evolve-config.py` / 命令路径并断言观测输出**;禁止 source-grep / read_text+assertIn / 建后即删;**变异:破坏行为 → 对应测试必须变红**。脚本必须真跑。
1. **已初始化根目录零参发现**:fixture target（带 `.bs-evolve/config.yaml`）下,从其根运行 `bs-evolve-config.py --emit-env`（无 `--config`）→ 导出的 env 与 `--config <该绝对路径>` **逐项一致**。变异:把 config 移走 → 发现失败、给出 init 提示。
2. **子目录也能发现**:从 target 的子目录运行 → 仍解析到 git 根的 config（不只根目录）。
3. **未初始化 fail-closed**:在一个无 `.bs-evolve/config.yaml` 的 git 仓里无 `--config` → 非零退出 + 提示含 `/bs-evolve-init`;**不** emit-env、**不**推导。变异:若有人加了「找不到就推导默认」分支,本测试要能抓到（断言它没 emit env）。
4. **非 git 目录** → 明确非零错误（非 traceback）。
5. **`--config` 覆盖仍工作**:显式 `--config <path>` 行为不变。
6. **wake_prompt 烧绝对路径**:零参发现路径下,emit 出的 `BS_LOOP_WAKE_PROMPT` 含**解析后的绝对 config 路径**（自链跨 CWD 不丢）。变异:改成相对/空 → 测试红。
7. 全套 `unittest` 绿 + `verify-manifest.sh` + `grade-fixture-walker.py`;改的 manifest 行已 relock。

## 明确 out-of-scope
- **不**为未初始化项目做纯约定推导（已定:提示去 init）。
- 不改 `/bs-evolve-init` 的约定/默认 mode（已 auto）。
- 不动 Stage B 并发机制。
- 测试只在 /tmp fixture 跑,**绝不**碰真 OpenSymphony,不 push 任何真 remote。

## 流程 + 返回
- 新分支、per-item commit、不重写历史。
- 返回:改了哪些文件、每条验收的真实证据(命令输出/测试名)、**每条变异自检结果**、unittest 全量。我再独立验收(变异 + 真跑)。
