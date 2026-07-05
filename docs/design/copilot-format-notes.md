# 抄作业作业格式调研笔记（M0）

调研日期：2026-07-04。本文档记录 AI 攻略导入 compiler 所依赖的**真实数据契约**，
对应 [ai-copilot-guide-import-plan.md](../plans/ai-copilot-guide-import-plan.md) 的 M0 里程碑。

## 1. 结论摘要

1. 作业站（share.maayuan.top）分发的作业是 **version 3 结构化格式**：
   元数据信封 + `actions` 字段（MaaFramework pipeline 节点字典，带 `text_doc` 简写标注）。
2. **compiler 的目标格式就是这个 v3 作业格式**，而不是自由发挥的 pipeline JSON。
   框架节点（回合检测、胜利、重开、暂停）由 `pipeline/copilot/copilot_config.json` 提供，
   作业只需要生成 `检测回合N` / `回合N行动M` 节点并接入框架节点。
3. 全部动作坐标基于 **720x1280 竖屏**，每个号位的普攻/大招/防御坐标见 §5。
4. 作业站 API 未认证即可 `query` / `get/{id}`，可持续获取评测样本。

## 2. 作业站 API

| 接口 | 说明 |
|---|---|
| `GET https://share.maayuan.top/api/copilot/query?page=N&limit=M` | 作业列表，`data.data[]` |
| `GET https://share.maayuan.top/api/copilot/get/{id}` | 单个作业，`data.content` 是 JSON 字符串 |
| `POST .../copilot/upload` 等 | 需要认证（`maa-copilot-auth`），首期不涉及 |

列表项字段：`id, name, stage_id, cat_one/two/three, tags, views, hot_score, rating_*, content`。
「神秘代码」即作业站上的作业 id，MFA GUI 导入时按 id 拉取 `content` 落盘。

## 3. v3 作业 content 顶层结构

```jsonc
{
  "version": 3,
  "stage_name": "qian_shang_hong",
  "difficulty": 0,
  "minimum_required": "v4.0.0",         // MaaYuan 最低版本
  "level_recognition_name": "3",        // 关卡识别用文字
  "level_meta": {
    "stage_id": "...", "level_id": "di_gong/qian_shang_hong",
    "name": "千觞红", "cat_one": "地宫", "cat_two": "...", "cat_three": "...",
    "width": 0, "height": 0
  },
  "doc": { "title": "...", "details": "..." },   // 展示用说明
  "opers": [                                      // 阵容（按站位顺序）
    {
      "name": "诸葛亮",
      "discs_selected": [3, 2, 0],                // 命盘
      "disc_star_stones": ["", "", ""],           // 星石
      "disc_assist_stars": ["", "", ""]           // 辅星
    }
  ],
  "groups": [],                                   // 备选干员组，常为空
  "level": "qian_shang_hong",
  "actions": { /* pipeline 节点字典，见 §4 */ }
}
```

注意：站上仍有大量**无 `version` 字段的旧作业**（视为 v1/v2），结构类似但字段有出入。
AI compiler 首期只生成 v3；旧格式无需支持。

## 4. actions 节点模式

`actions` 是标准 MaaFramework pipeline 节点，外加两个作业专用字段：

- `text_doc`：单元格简写（如 `1普`、`3下`、`2大`、`等待`、`右侧目标`），编辑器 V2 表格视图直接展示；
- `focus`：执行时的用户提示文案。

### 4.1 回合检测节点（每回合一个）

```jsonc
"检测回合1": {
  "recognition": "Custom",
  "custom_recognition": "PureNum",              // agent/custom/reco/purenum.py
  "custom_recognition_param": { "roi": [641, 50, 43, 27], "expected": "1" },
  "text_doc": "回合1",
  "focus": "当前：第1回合",
  "next": ["史子眇sp", "回合1行动1"],
  "on_error": ["抄作业点左上角重开"],
  "timeout": 3000,
  "post_delay": 4000
}
```

### 4.2 动作节点（每回合内按顺序链接）

```jsonc
// 普攻 = Click
"回合1行动4": {
  "action": "Click", "target": [56, 1060, 5, 5],
  "post_delay": 3000, "text_doc": "1普", "focus": "行动:1号位普攻",
  "next": ["史子眇sp", "回合1行动5"]
}
// 大招 = 上划 Swipe（y: 1060 -> ~670）
"回合2行动1": {
  "action": "Swipe", "begin": [77, 1060, 10, 1], "end": [77, 670, 10, 1],
  "duration": 800, "post_delay": 5000, "text_doc": "1大", "focus": "行动:1号位大招",
  "next": ["史子眇sp", "回合2行动2"]
}
// 防御 = 下划 Swipe（y: 1060 -> ~1240-1258）
// 等待 = 空节点只有 post_delay
"回合1行动2": { "text_doc": "等待", "focus": "等待3000ms", "post_delay": 3000, "next": [...] }
// 切换目标 = Click 敌方头顶箭头
"回合1行动1": { "text_doc": "右侧目标", "action": "Click", "target": [603, 413, 18, 21], ... }
```

### 4.3 回合收尾与循环

每回合**最后一个动作**的 `next` 接回框架节点：

```jsonc
"next": ["史子眇sp", "抄作业全灭重开", "抄作业战斗胜利", "检测回合2"]
```

- 胜利/全灭分支靠框架节点识别；
- 循环 = `next` 指回更早的 `检测回合N`（配合 PureNum 的 expected 判断）；
- 条件分支 = 插入识别节点（如 `第3回合橙星检测` ColorMatch），
  识别失败走 `on_error`（常为 `抄作业点左上角重开`）。

### 4.4 观察到的字段全集

`action, begin, end, duration, target, roi, recognition, custom_recognition,
custom_recognition_param, expected, template, threshold, green_mask, upper, lower,
next, on_error, timeout, pre_delay, post_delay, attack_delay, defense_delay, ult_delay,
text_doc, focus`

## 5. 号位坐标表（720x1280）

来自 3 份 golden 作业的实测值（同类动作坐标在不同作业中一致）：

| 号位 | 普攻 Click target | 大招 Swipe begin→end | 防御 Swipe begin→end |
|---|---|---|---|
| 1 | [56, 1060, 5, 5] | [77,1060]→[77,670] | [73,1060]→[73,1258] |
| 2 | [180, 1060, 5, 5] | [220,1060]→[225,668] | [221,1060]→[221,1251] |
| 3 | [357, 1060, 5, 5] | [357,1060]→[357,714] | [357,1060]→[357,1237] |
| 4 | [496, 1060, 5, 5] | [496,1060]→[496,679] | [496,1060]→[496,1258] |
| 5 | [646, 1060, 5, 5] | [646,1060]→[642,700] | [646,1060]→[646,1258] |

Swipe `duration` 均为 800。目标切换：右侧 [603,413,18,21]（左侧对称）。
「点圈切换状态」在本次抽样 20 份作业中未出现，坐标待后续样本确认。

## 6. 框架节点契约（copilot_config.json）

作业生成节点可以引用的系统节点：

| 节点 | 作用 |
|---|---|
| `抄作业启动位置` | 入口，CustomAction `CopilotInfo` 打印作业信息 |
| `抄作业准备开始战斗` / `抄作业战斗开始` | 进关与切手动 |
| `抄作业-默认开始回合数` | PureNum 检测回合 1 后进入 `替代-检测回合1` |
| `替代-检测回合1` | **空占位节点，由作业文件 override**（作业的接入点） |
| `抄作业战斗胜利-check` / `抄作业战斗胜利` | 胜利识别与确认 |
| `抄作业全灭重开` | OCR「再次挑战」自动重开 |
| `抄作业点左上角重开` / `抄作业确定左上角重开` | 主动重开 |
| `抄作业暂停提醒` | focus + toast 通知 |
| `史子眇sp` | is_sub 子节点：TemplateMatch 到 sp 技能则点击 |

回合数识别：PureNum custom reco，`roi: [641, 50, 43, 27]`，OCR model `en`、`only_rec`。
阵亡检测：CustomAction `DownRestart`（`agent/custom/action/copilotinfo.py`），
ColorMatch 各号位血条区域，检测到阵亡则 `override_next` 到左上角重开。

## 7. Compiler compatibility matrix（初版）

| IR 能力 | v3 作业表达 | 状态 |
|---|---|---|
| attack / ultimate / defend | Click / Swipe 上 / Swipe 下（§5 坐标） | 已确认 |
| wait | 空节点 + post_delay | 已确认 |
| select_enemy（左右侧目标） | Click 箭头坐标 | 已确认 |
| switch_state（点圈） | 未在样本中出现 | 待确认 |
| 回合推进 | `检测回合N` PureNum + 链式 next | 已确认 |
| 循环 | next 指回早期检测节点 | 已确认（29181 等） |
| 条件分支（橙星/紫星检测） | 识别节点 + on_error | 已确认 |
| 阶段切换 | 无一等公民，需用识别节点模拟 | 需 IR→多节点展开 |
| restart | `抄作业点左上角重开` | 已确认 |
| pause | `抄作业暂停提醒` | 已确认 |

## 8. Golden reference fixtures

`tests/fixtures/ai_copilot/existing_jobs/`：

- `29241_basic_actions_and_color_check.json` — 普/大/下 + 橙星条件检测 + 重开策略；
- `29182_target_switching.json` — 左右侧目标切换 + 多阶段回合表；
- `29188_waits_and_ordering.json` — 等待动作与动作顺序控制。

fixture 外层 `_fixture` 记录来源与抓取日期，`content` 为解码后的 v3 作业原文
（已去除上传者账号信息）。

## 9. 待确认项（不阻塞 M1/M2）

1. 点圈（switch_state）节点的真实坐标与写法 —— 需找到含圈的作业样本；
2. MFA GUI「神秘代码」导入后作业文件的本地落盘路径（在 MFA GUI 仓库，非本仓库）；
3. 编辑器 V2 是否对 `actions` 之外的字段有额外要求；
4. `groups`（备选干员组）的完整语义；
5. 旧版（无 version 字段）作业是否需要只读兼容。
