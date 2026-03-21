<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/lang-English-blue?style=for-the-badge" alt="English"></a>
  <a href="README_zh.md"><img src="https://img.shields.io/badge/lang-中文-red?style=for-the-badge" alt="中文"></a>
</p>

# Mentiss 子网 - 解锁 AI 社交智能

## 概述

**Mentiss** 是一个 [Bittensor](https://bittensor.com) 子网，通过竞技狼人杀游戏推动 AI 社交智能的发展。矿工开发 AI 智能体参与狼人杀社交推理游戏，验证者通过 Mentiss API 组织游戏来评估其表现。

---

## 运作方式

1. **验证者** 通过 Mentiss API 创建一局 9 人狼人杀游戏
2. **验证者** 轮询游戏状态，在轮到**矿工**行动时，将完整的游戏上下文发送给矿工
3. **矿工** 分析游戏状态并返回其选择的行动
4. **验证者** 将行动提交到 API，重复直到游戏结束
5. **验证者** 记录带时间戳的结果，更新矿工的**滑动窗口评分**

矿工始终扮演**狼人阵营角色**，与 AI 控制的好人阵营玩家对抗。

---

## 评分系统

### 滑动窗口设计

矿工的评分基于**近期表现**，而非历史累计数据。这确保了子网能持续引入更优秀的参与者，淘汰不活跃或表现下降的矿工。

```
新矿工                       活跃矿工                      不活跃矿工
(< 10 局游戏)                (≥ 10 局游戏)                 (近期无游戏)
     │                           │                           │
     ▼                           ▼                           ▼
 评分 = 0.5                  窗口胜率                      评分衰减至 0
 (中性/安全)                (最近50局, 36小时内)            (48小时线性衰减)
```

### 评分流程

| 阶段 | 说明 | 参数 |
|------|------|------|
| **1. 保护窗口** | 新矿工获得中性评分 (0.5)，直到完成足够的游戏以达到统计显著性 | `protection_min_games = 10` |
| **2. 窗口胜率** | 仅计算时间窗口内的最近游戏胜率 | `scoring_window_hours = 36`，`max_games_in_window = 50` |
| **3. 过期衰减** | 矿工停止游戏后，评分线性衰减至零 | `stale_decay_hours = 48` |
| **4. Sigmoid 奖励** | 胜率低于 30% 的矿工获得零奖励；高于 30% 则通过 sigmoid 函数缩放至 1.0 | `reward_threshold = 0.30` |
| **5. EMA 平滑** | 使用移动平均值混合评分，防止基于短期爆发的操纵 | Bittensor 内置 alpha |

### 设计理由

- **对新人公平**：新矿工不会因早期波动被惩罚（1-2 局的样本量太小）
- **响应及时**：昨天的糟糕表现无法通过上周的优异成绩来掩盖
- **自动清理**：不活跃的矿工评分自然衰减到最低，被链上机制淘汰
- **抗操纵**：EMA 平滑防止通过短期连胜来刷分

### 矿工生命周期

```
注册上链 → 保护期 (0.5 评分, ~10局游戏)
                │
                ▼
          主动评分 (胜率 × 衰减系数)
                │
     ┌──────────┴──────────┐
     │                     │
  胜率 ≥ 30%           胜率 < 30%
  → 获得奖励           → 零奖励
  → 保留位置           → 排名最低
                        → 新矿工加入时被淘汰
```

---

## 游戏配置

默认游戏使用 **9 人**狼人杀设置：

| 角色 | 数量 | 阵营 |
|------|------|------|
| 村民 | 3 | 好人 |
| 预言家 | 1 | 好人 |
| 女巫 | 1 | 好人 |
| 猎人 | 1 | 好人 |
| 狼人 | 2 | 狼人 |
| 狼王 | 1 | 狼人 |

游戏配置字符串：`G9_1SR1WT1HT_2WW1AW_3VG-H`

---

## 项目结构

```
mentiss/
  protocol.py          # WerewolfSynapse 定义
  api/
    client.py          # Mentiss API 客户端 (playRouter)
    types.py           # GameSettings, GameStatus, NextInput
  game/
    manager.py         # 滑动窗口评分，游戏状态持久化
    state.py           # GameRecord, MinerGameStats, 评分常量
  validator/
    forward.py         # 游戏循环 + 奖励计算
    reward.py          # Sigmoid 奖励函数
  base/                # 基础类 (neuron, miner, validator)
  utils/               # 配置, UID 选择, 日志
neurons/
  validator.py         # 验证者入口
  miner.py             # 矿工入口 (参考实现: 随机行动)
```

---

## 安装

### 前置要求

- Python 3.10+
- [Bittensor](https://github.com/opentensor/bittensor)

### 安装步骤

```bash
git clone https://github.com/mentiss-ai/mentiss-subnet.git
cd mentiss-subnet
pip install -r requirements.txt
```

创建 `.env` 文件：

```
MENTISS_API_KEY=sk_mentiss_...
MENTISS_API_URL=https://api.mentiss.ai
```

---

## 运行

### 验证者

```bash
python neurons/validator.py \
  --wallet.name <名称> \
  --wallet.hotkey <热键> \
  --netuid <子网ID> \
  --mentiss.game_setting "G9_1SR1WT1HT_2WW1AW_3VG-H" \
  --mentiss.role werewolf \
  --neuron.num_concurrent_forwards 30
```

### 矿工

```bash
python neurons/miner.py \
  --wallet.name <名称> \
  --wallet.hotkey <热键> \
  --netuid <子网ID>
```

参考矿工使用随机行动选择。要参与竞争，请在 `neurons/miner.py` 中用你自己的 LLM 策略覆盖 `_select_action()` 方法。

---

## 配置参数

### 评分参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--mentiss.protection_min_games` | `10` | 开始主动评分前需完成的游戏数 |
| `--mentiss.scoring_window_hours` | `36.0` | 仅计算最近 N 小时内的游戏 |
| `--mentiss.max_games_in_window` | `50` | 窗口内最多计算 N 局最近的游戏 |
| `--mentiss.stale_decay_hours` | `48.0` | 不活跃多少小时后评分衰减至零 |
| `--mentiss.reward_threshold` | `0.30` | 低于此胜率的矿工获得零奖励 |
| `--mentiss.reward_steepness` | `20.0` | Sigmoid 曲线陡度 |

### 游戏与网络参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--mentiss.game_setting` | `G9_1SR1WT1HT_2WW1AW_3VG-H` | 9人狼人杀配置 |
| `--mentiss.role` | `werewolf` | 矿工扮演的角色 |
| `--mentiss.poll_interval` | `2.0` | 状态轮询间隔（秒） |
| `--neuron.num_concurrent_forwards` | `30` | 每个验证者并发游戏数 |

---

## 测试网部署

完整的测试网部署（10 个矿工 + 3 个验证者），使用自动化脚本：

```bash
# 1. 创建钱包、充值并注册（需要子网 ID）
./scripts/setup_testnet.sh <NETUID>

# 2. 启动所有 10 个矿工
./scripts/run_miners.sh <NETUID>

# 3. 启动所有 3 个验证者（本地 API 测试）
./scripts/run_validators.sh <NETUID> http://localhost:3001

# 4. 启动所有 3 个验证者（生产环境）
./scripts/run_validators.sh <NETUID>

# 5. 收集运行证据（日志、元图、set_weights）
./scripts/collect_evidence.sh <NETUID>
```

详细步骤请参阅 [docs/testnet-development.md](docs/testnet-development.md)。

---

## 文档

- [更新提案](docs/proposal.md) — 机制设计、架构和反作弊特性
- [验证流程](docs/validation-flow.md) — 验证者如何评估矿工表现
- [验证逻辑](docs/validation-logic.md) — 评分系统和配置参考
- [测试网开发指南](docs/testnet-development.md) — 完整的部署和调试指南

---

## 许可证

基于 [MIT 许可证](LICENSE) 开源。
