# AI 攻略导入与作业生成实施计划

## 1. 实施原则

本计划建立在 MaaYuan 已有能力之上：

- 模拟器连接和控制；
- OCR、模板匹配和颜色识别；
- 回合检测；
- 普攻、上拉、下拉和点击状态圈；
- 战斗胜利检测；
- 全灭重开；
- 作业导入与编辑；
- 作业站分享。

不重复实现执行层。首期只增加：

1. 攻略输入；
2. AI/OCR 解析；
3. 中间表示；
4. 人工确认；
5. 静态校验；
6. 编译为现有作业格式；
7. 诊断和测试工具。

## 2. 总体架构

```text
攻略图片 / 攻略文字
        |
        v
Source Ingestion
        |
        v
Layout + OCR + VLM Parser
        |
        v
Normalized IR
        |
        +--> Uncertainty Review UI
        |
        v
Static Validator
        |
        v
MaaYuan Copilot Compiler
        |
        v
现有作业编辑器 / 抄作业执行器
```

建议将 AI 导入功能设计为独立模块，不让模型直接修改系统 pipeline。

## 3. 目录建议

最终目录根据现有项目结构调整，建议先按以下边界实现：

```text
agent/
  ai_copilot/
    __init__.py
    schema.py
    parser.py
    normalizer.py
    validator.py
    compiler.py
    diagnostics.py
    providers/
      base.py
      openai_compatible.py
      local.py
    prompts/
      guide_image.md
      guide_text.md

assets/
  resource/base/pipeline/ai_copilot/
    ai_copilot_entry.json

src/ or UI project/
  pages/ai-copilot-import/
  viewmodels/ai-copilot-import/

tests/
  ai_copilot/
  fixtures/ai_copilot/

docs/
  design/ai-copilot-guide-import-spec.md
  plans/ai-copilot-guide-import-plan.md
```

若 GUI 项目当前不便直接加入复杂页面，可先实现独立本地 Web UI 或命令行原型，验证数据链路后再集成。

## 4. 里程碑

## M0：仓库调研和格式冻结

### 目标

明确当前作业文件、编辑器和执行器的真实数据契约，避免基于假设实现 compiler。

### 任务

- [ ] 找到现有作业文件的完整 schema 或代表性样例；
- [ ] 记录基础动作对应的 pipeline 节点；
- [ ] 记录回合检测、目标选择、状态圈和重开节点；
- [ ] 确认作业编辑器 V2 的输入输出格式；
- [ ] 确认作业站导入“神秘代码”后的本地文件格式；
- [ ] 确认用户作业目录和加载流程；
- [ ] 确认是否已有 JSON schema 或验证逻辑；
- [ ] 建立 compiler compatibility matrix；
- [ ] 选取 3 份现有可运行作业作为 golden reference。

### 交付物

- `docs/design/copilot-format-notes.md`
- `tests/fixtures/ai_copilot/existing_jobs/`
- 一份最小手写 IR 到现有作业的映射样例

### 验收

能够手工编写一份 IR，并通过临时脚本生成与现有作业语义等价的 JSON。

---

## M1：IR Schema 与静态校验器

### 目标

先建立稳定、可测试的数据层，不接入任何 AI 模型。

### 任务

- [ ] 定义 `schema_version = 1`；
- [ ] 定义 metadata、party、phase、turn plan、rule、condition、repeat group；
- [ ] 定义基础动作枚举；
- [ ] 定义条件动作和 fallback；
- [ ] 定义字段级 confidence 和 evidence；
- [ ] 定义 uncertainty 数据结构；
- [ ] 使用 Pydantic 或等价方案做 schema 校验；
- [ ] 实现静态校验器；
- [ ] 实现稳定的错误代码；
- [ ] 编写 JSON/YAML 序列化和反序列化；
- [ ] 编写 schema migration 接口，占位支持后续版本。

### 建议错误代码

```text
IR001 INVALID_SLOT
IR002 DUPLICATE_ACTION_SEQUENCE
IR003 UNKNOWN_OPERATOR
IR004 MISSING_FALLBACK
IR005 UNBOUNDED_LOOP
IR006 UNRESOLVED_UNCERTAINTY
IR007 UNKNOWN_TARGET
IR008 UNREACHABLE_PHASE
IR009 DUPLICATE_NODE_NAME
IR010 NO_TERMINATION_PATH
```

### 测试

- 正常五人五动作；
- 某回合角色缺失；
- 动作顺序重复；
- 循环没有终止条件；
- 条件动作没有 fallback；
- 阶段不可达；
- 未解决歧义阻止编译。

### 交付物

- `agent/ai_copilot/schema.py`
- `agent/ai_copilot/validator.py`
- `tests/ai_copilot/test_schema.py`
- `tests/ai_copilot/test_validator.py`

### 验收

不依赖网络和模型，所有 schema 与校验测试通过。

---

## M2：MaaYuan Compiler MVP

### 目标

把人工编写的 IR 编译为 MaaYuan 可加载、可执行的作业文件。

### 第一批支持范围

- 普攻；
- 上拉大招；
- 下拉防御；
- 固定位置点击状态圈；
- 固定我方/敌方目标选择；
- 回合表；
- 固定次数循环；
- 阶段切换后的不同回合计划；
- 暂停；
- 重开；
- 有大开大，否则普攻。

### 暂不支持

- 任意自然语言条件；
- 复杂血量阈值；
- 未录入的状态图标；
- 动态敌方排序；
- 自动替换阵容。

### 任务

- [ ] 建立 IR action 到现有节点的映射；
- [ ] 为生成节点增加唯一前缀；
- [ ] 保留 `source_id -> generated_node` 映射；
- [ ] 实现回合节点生成；
- [ ] 实现动作顺序链；
- [ ] 实现条件动作分支；
- [ ] 实现循环和最大次数保护；
- [ ] 实现阶段入口和退出；
- [ ] 实现胜利、全灭和暂停终止路径；
- [ ] 编译后执行第二次结构校验；
- [ ] 支持输出到临时目录；
- [ ] 支持导入现有作业编辑器。

### 测试

- IR snapshot tests；
- compiler deterministic tests；
- generated JSON schema tests；
- 与 3 份现有作业进行语义对照；
- 在模拟器中执行最简单真实关卡。

### 交付物

- `agent/ai_copilot/compiler.py`
- `tests/ai_copilot/test_compiler.py`
- `tests/fixtures/ai_copilot/compiler/`

### 验收

一份手写 IR 能够生成作业，并通过现有 MaaYuan 完成至少一个真实关卡。

---

## M3：文字攻略解析 MVP

### 目标

先支持纯文字攻略，降低图片版面识别的复杂度。

### 输入示例

```text
1回合全员普攻。
2回合颜良开大，王粲有大开大，否则普攻，史子眇防御。
Boss 开大时选 5 号位。
史子眇开大后下一位防御。
1、2回合循环到一命结束。
```

### 任务

- [ ] 定义模型 provider 抽象；
- [ ] 支持 OpenAI-compatible endpoint；
- [ ] 支持自定义 base URL、model、API key；
- [ ] 设计 JSON schema constrained output；
- [ ] 编写文字攻略 prompt；
- [ ] 实现操作符别名和符号词典；
- [ ] 实现模型结果到 IR 的 normalizer；
- [ ] 生成 uncertainty 列表；
- [ ] 对未知角色、目标和符号做强制确认；
- [ ] 实现模型重试和超时；
- [ ] 对模型返回做严格 schema 校验；
- [ ] 禁止模型直接输出系统 pipeline。

### 测试集

至少 20 条文字攻略，覆盖：

- 简单逐回合；
- 有大开大；
- 下一位防御；
- 指定目标；
- 阶段切换；
- 循环；
- 矛盾描述；
- 未知缩写；
- 角色别名；
- 不完整攻略。

### 交付物

- `agent/ai_copilot/providers/`
- `agent/ai_copilot/parser.py`
- `agent/ai_copilot/normalizer.py`
- `agent/ai_copilot/prompts/guide_text.md`

### 验收

对测试集中的明确基础动作，单元格动作准确率达到 95%；所有未知符号进入 uncertainty，不被静默接受。

---

## M4：图片攻略解析 MVP

### 目标

支持类似回合表、阵容头像和备注区组成的单张攻略图。

### 技术路线

采用混合识别：

1. OpenCV 做基础裁切和表格线检测；
2. OCR 提取文字；
3. VLM 理解复杂布局和备注关联；
4. 角色名称优先结合用户选择的阵容做候选约束；
5. 最终由 normalizer 生成 IR。

不要求首期训练自有视觉模型。

### 任务

- [ ] 图片上传和本地临时存储；
- [ ] EXIF 方向校正；
- [ ] 图片尺寸和格式校验；
- [ ] 表格区域检测；
- [ ] 回合行和角色列检测；
- [ ] OCR 接口；
- [ ] VLM 图片解析 prompt；
- [ ] 多图合并；
- [ ] 证据区域坐标；
- [ ] 将 OCR 与 VLM 结果合并；
- [ ] 阵容候选约束；
- [ ] 冲突结果进入 uncertainty；
- [ ] 图片生命周期清理。

### Golden dataset

首批至少 30 张：

- 标准表格 10 张；
- 表格加备注 10 张；
- 低清或压缩图 5 张；
- 非标准排版 5 张。

每张标注：

- 阵容；
- 回合；
- 单元格动作；
- 顺序；
- 目标；
- 阶段；
- 规则；
- 应强制确认项。

### 交付物

- `agent/ai_copilot/prompts/guide_image.md`
- 图片预处理模块；
- OCR/VLM parser；
- `tests/fixtures/ai_copilot/images/`

### 验收

标准表格基础动作识别准确率达到 95%；复杂备注允许较低自动填充率，但强制确认召回率应优先达到 95%。

---

## M5：确认与编辑 UI

### 目标

让用户能在生成作业前快速修正解析结果，而不是编辑底层 JSON。

### 页面一：导入

- [ ] 图片上传；
- [ ] 文字粘贴；
- [ ] 游戏版本；
- [ ] 关卡；
- [ ] 阵容和站位；
- [ ] 模型配置；
- [ ] 解析按钮；
- [ ] 隐私提示。

### 页面二：确认

- [ ] 原图预览；
- [ ] 回合表；
- [ ] 全局规则；
- [ ] 阶段规则；
- [ ] 置信度；
- [ ] uncertainty 列表；
- [ ] 点击单元格定位证据区域；
- [ ] 批量确认中置信度项；
- [ ] 未解决项计数；
- [ ] 实时静态校验。

### 页面三：生成

- [ ] 校验摘要；
- [ ] 作业名称；
- [ ] JSON 预览；
- [ ] 保存到本地；
- [ ] 导入作业编辑器；
- [ ] 复制；
- [ ] 下载；
- [ ] 返回修改。

### 可访问性和可用性

- 不只用颜色表达置信度；
- 所有错误有文本说明；
- 支持键盘操作；
- 用户离开页面前提示未保存修改；
- AI 解析失败时仍可手工补录。

### 验收

新用户可在不打开 JSON 的情况下，从图片完成解析、确认和生成。

---

## M6：运行诊断与保护

### 目标

确保 AI 生成作业失败时可追踪、可停止，不会持续误操作。

### 任务

- [ ] 保存作业 ID、IR 版本和 compiler 版本；
- [ ] 记录当前阶段、回合和动作序号；
- [ ] 保存最近 N 个动作；
- [ ] 失败时截屏；
- [ ] 记录识别节点及分数；
- [ ] 生成诊断包；
- [ ] 未知界面暂停；
- [ ] 回合不匹配暂停；
- [ ] 连续无画面变化暂停；
- [ ] 循环达到上限暂停；
- [ ] 意外阵亡按配置重开或暂停；
- [ ] 统一紧急停止行为。

### 诊断包建议

```text
diagnostic-<timestamp>/
  manifest.json
  source.ir.yaml
  compiled_job.json
  execution.log
  last_screen.png
  recognition.json
```

### 验收

任意测试失败都能定位到：原始 IR、生成节点、失败回合和最后截图。

---

## M7：Beta 与作业站集成

### 目标

让生成作业能够进入现有分享生态，同时避免低质量 AI 作业直接污染公共列表。

### 任务

- [ ] 作业元数据标记 `generated_by_ai`；
- [ ] 保存模型、prompt 和 compiler 版本；
- [ ] AI 作业默认保存为草稿；
- [ ] 至少一次本地成功运行后才允许公开；
- [ ] 上传前提示删除原攻略图片和个人信息；
- [ ] 作业站支持展示“AI 生成，已人工确认”；
- [ ] 支持用户提交解析修正反馈；
- [ ] 统计首次运行成功率；
- [ ] 建立模型成本和限流策略。

### 验收

Beta 用户可以生成、验证并分享作业；公共作业明确展示来源和验证状态。

## 5. 分阶段 PR 策略

避免一个超大 PR，建议按以下顺序拆分：

### PR 1：Design docs

- 本 spec；
- 本 implementation plan；
- 不包含运行时代码。

### PR 2：IR schema + validator

- 数据模型；
- 静态校验；
- 单元测试；
- 示例 IR。

### PR 3：Compiler MVP

- 基础动作；
- 回合和顺序；
- 生成 JSON；
- snapshot tests。

### PR 4：Text parser

- provider interface；
- prompt；
- structured output；
- uncertainty。

### PR 5：Image parser

- 上传；
- OCR/VLM；
- evidence regions；
- golden tests。

### PR 6：Review UI

- 导入；
- 确认；
- 校验；
- 生成。

### PR 7：Diagnostics

- 执行追踪；
- 诊断包；
- 安全暂停。

### PR 8：Job station integration

- AI metadata；
- 草稿；
- 验证状态；
- 分享流程。

## 6. 任务优先级

### P0

- IR schema；
- validator；
- compiler；
- 文字攻略解析；
- 图片标准表格解析；
- 人工确认；
- 生成现有作业；
- 安全暂停。

### P1

- 多图合并；
- 证据区域定位；
- 诊断包；
- 作业站草稿；
- 阵容属性要求；
- 个性化符号词典。

### P2

- 视频解析；
- 运行失败 AI 建议；
- 相似作业召回；
- 多模型评审；
- 自动替换阵容；
- 未知关卡有限规划。

## 7. 技术决策

### 7.1 Provider 抽象

必须支持 OpenAI-compatible API，而不是绑定单一厂商：

```python
class GuideParserProvider(Protocol):
    async def parse_text(self, request: TextGuideRequest) -> ParsedGuide:
        ...

    async def parse_images(self, request: ImageGuideRequest) -> ParsedGuide:
        ...
```

### 7.2 Schema constrained output

能使用 JSON Schema constrained decoding 时必须启用。不能依赖“请输出 JSON”这种软约束。

### 7.3 本地优先

- 图片预处理本地执行；
- IR、用户修正和作业保存在本地；
- 仅模型所需内容发送到远程；
- 用户可关闭远程 AI。

### 7.4 不直接生成 pipeline

模型只输出 ParsedGuide/IR。Compiler 是唯一允许生成 MaaYuan 作业节点的模块。

### 7.5 可复现性

保存：

- 模型名称；
- provider；
- prompt 版本；
- schema 版本；
- compiler 版本；
- 用户确认记录。

## 8. 测试和质量门槛

### 8.1 CI 必须执行

- formatter；
- linter；
- type checking；
- schema tests；
- validator tests；
- compiler snapshot tests；
- parser fixture tests；
- 敏感信息扫描。

### 8.2 合并门槛

- 新逻辑有单元测试；
- compiler 变更有 snapshot 更新说明；
- schema 变更有 migration；
- prompt 变更有 fixture 评测；
- 不降低强制确认召回率；
- 不允许把 API key 写入配置样例；
- 不允许新增无上限循环。

## 9. 评测方案

### 9.1 数据划分

- Train/dev：用于 prompt 和规则调整；
- Test：固定，不用于调 prompt；
- Regression：每次线上失败后加入。

### 9.2 核心指标

```text
cell_action_accuracy
sequence_accuracy
target_accuracy
phase_rule_accuracy
mandatory_review_recall
incorrect_auto_accept_rate
average_user_edits
compile_success_rate
first_run_success_rate
```

### 9.3 MVP 目标

- 基础动作准确率 >= 95%；
- 动作顺序准确率 >= 95%；
- 强制确认召回率 >= 95%；
- 错误自动接受率 <= 1%；
- compiler 成功率 >= 99%；
- 10 份标准攻略中至少 8 份只需少量人工修改即可生成。

## 10. 风险和缓解

### 风险 1：攻略缩写高度个性化

缓解：

- 用户级符号词典；
- 候选解释；
- 低置信度强制确认；
- 保存作者模板。

### 风险 2：攻略图片分辨率和排版差异大

缓解：

- 先支持标准表格；
- 使用阵容候选约束；
- OCR 与 VLM 交叉验证；
- 允许手工框选表格；
- 保留纯文字导入兜底。

### 风险 3：MaaYuan 作业格式变化

缓解：

- 独立 IR；
- versioned compiler；
- compatibility matrix；
- golden jobs。

### 风险 4：模型幻觉导致错误动作

缓解：

- schema constrained output；
- 静态校验；
- evidence；
- uncertainty；
- 人工确认；
- 不直接生成 pipeline。

### 风险 5：运行时状态和攻略不一致

缓解：

- 回合检测；
- 最大循环次数；
- 目标确认；
- 画面变化确认；
- 暂停保护；
- 诊断包。

### 风险 6：远程模型成本和隐私

缓解：

- provider 抽象；
- 本地模型选项；
- 图片压缩；
- 缓存；
- 明确隐私提示；
- 默认不永久保存图片。

## 11. 开发顺序建议

最小闭环按以下顺序推进：

```text
M0 格式调研
  -> M1 IR + validator
  -> M2 手写 IR compiler
  -> M3 文字攻略解析
  -> 简单确认 UI
  -> M4 图片标准表格
  -> M6 诊断保护
  -> M5 完整 UI
  -> M7 作业站
```

不要先做复杂 VLM 页面，再补 compiler。只有“手写 IR 能稳定跑通现有执行器”后，AI 解析才有可靠输出目标。

## 12. 第一迭代建议

第一迭代控制在一个窄范围：

### 支持

- 单张标准表格截图；
- 固定 5 人阵容；
- 回合 1-20；
- 普攻、上拉、下拉、点圈；
- 固定目标；
- 有大开大否则普攻；
- 简单 1-2 回合循环；
- 人工确认；
- 导出作业。

### 不支持

- 视频；
- 多阶段复杂条件；
- 血量识别；
- 任意状态图标；
- 自动修复；
- 无攻略自主通关。

### 第一迭代完成定义

用户上传一张标准攻略图，确认少数歧义后，能够生成作业并由 MaaYuan 在固定模拟器配置中完成一场真实战斗。
