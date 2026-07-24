---
name: wewrite-visual
description: |
  WeWrite 视觉模块：为公众号文章生成封面和必要的内文配图，或只交付提示词。触发词：
  封面图、公众号配图、给文章配图、换封面。通用绘图和 logo 设计不触发。
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Skill
---

# wewrite-visual — 封面与配图

## 前置

用户指定文章时使用该文件；否则 `wewrite run show`，读取当前任务的 `artifacts.article`、
`artifacts.illustrated_article`、`artifacts.image_prompts`、`artifacts.images_manifest`、
`visual`、`flags` 和任务目录。已完成的文章也可以直接配图，不要恢复或新建写作任务。

有任务时运行 `wewrite run step visual in_progress`。用户直接给了任务外文章时独立执行，
不写任务状态；提示词和图片放进文章同目录的 `<文件名>-assets/`，带图副本写成
`<文件名>-illustrated.md`。

根据本轮原话确定模式并用 `wewrite run update` 记录：只要封面用 `cover`，封面和必要内文图
用 `full`，只要提示词用 `prompts`。不要沿用写作模式猜测用户想生图。

## 核心原则

**本模块是编排层，不是执行层。** 封面的创意判断（类型、色板、渲染风格、文字层次、情绪）
和配图的视觉设计（类型 × 风格 × 色板）由 baoyu 技能家族完成。本模块负责：

1. 管理 wewrite 任务状态和产物路径
2. 将文章内容和约束传递给 baoyu 技能
3. 将 baoyu 产出映射回 wewrite 的 artifact 模型
4. 执行 wewrite 特有的后处理：带图副本插入、任务状态更新

baoyu 技能有自己的确认流程和交互设计 —— 不要跳过或压制它们的用户交互。

## 执行

### 1. 准备上下文

从 `artifacts.article` 读取终稿全文。确认以下约束并记录：

- `visual.max_images`：最大配图数量
- `visual.max_cost`：最大费用（为空则不限）
- 文章主题、情绪基调（用于传递给 baoyu 技能作为上下文）

将文章路径、主题摘要和约束写入任务目录下的 `visual-context.md` 供 baoyu 技能引用：

```markdown
# 配图上下文
- 文章路径: {article_path}
- 主题: {topic_summary}
- 情绪: {mood}
- 模式: {cover|full|prompts}
- 最大配图数: {max_images}
- 费用上限: {max_cost or "无"}
```

### 2. 按模式执行

#### cover 模式

调用 `baoyu-cover-image` skill，传递：
- 文章内容（文件路径或粘贴正文）
- 封面比例 2.35:1（WeChat 封面标准）
- 文章主题和情绪作为风格参考

baoyu-cover-image 会完成：偏好加载 → 内容分析 → 选项确认 → 提示词生成 → 图片生成。
完成后收集产出：

1. 读取 baoyu 生成的封面图片路径
2. 将提示词写入 `artifacts.image_prompts`（格式见第 3 节）
3. 将封面信息写入 `artifacts.images_manifest`
4. 将封面图片复制/移动到 wewrite 任务目录

#### full 模式

**先封面，后内文配图** —— 两步独立执行，共享风格上下文。

**步骤 A：封面**
同 cover 模式，调用 `baoyu-cover-image`。记录其确定的色板、渲染风格，作为后续内文配图的风格输入。

**步骤 B：内文配图**
调用 `baoyu-article-illustrator` skill，传递：
- 文章内容（文件路径或粘贴正文）
- 最大配图数 = `visual.max_images`
- 风格偏好：沿用封面确定的色板和渲染风格以保持视觉一致性
- 输出目录：wewrite 任务目录

baoyu-article-illustrator 会完成：偏好加载 → 内容分析 → 插图位置识别 → 选项确认 →
大纲生成 → 提示词生成 → 批量生图。完成后收集产出：

1. 读取 baoyu 生成的配图文件和路径
2. 将提示词写入 `artifacts.image_prompts`
3. 将配图清单写入 `artifacts.images_manifest`
4. 将封面和配图信息写入任务状态

**步骤 C：插入内文图**
先复制 `artifacts.article` 到 `artifacts.illustrated_article`，再将采用的
内文图插到副本相应段落；封面不插入正文。任何模式都不得覆盖原始正文。

#### prompts 模式

执行对应的 baoyu 技能流程，但在生图步骤前停止。收集生成的提示词文本，
写入 `artifacts.image_prompts`，明确告知用户提示词已就绪、未产生费用、
没有实际图片。`skip_image_gen=true` 时同样处理。

### 3. 产物格式

`artifacts.image_prompts` 写入 Markdown：

```markdown
# 图片提示词 — {date}

## 封面
- 提示词: {cover_prompt}
- 目标比例: 2.35:1

## 内文图
1. {position}: {prompt} → {output_path}
2. ...
```

`artifacts.images_manifest` 写入 JSON：

```json
{
  "cover": {"prompt": "...", "path": "cover.png", "ok": true},
  "figures": [
    {"position": "...", "prompt": "...", "path": "figure-01.png", "ok": true}
  ]
}
```

### 4. 质量检查与收尾

- 一次性检查所有实际文件：能打开、格式与扩展名一致、核心实体可辨、风格连贯
- 只重试明显失败的单张一次
- 数量必须不超过 `visual.max_images`；超限时按必要性排序，只保留前 N 张
- 费用预检不通过就减少内文图，不能绕过上限
- 图片服务失败时保留完整提示词并继续流程

完成后更新 `images.cover`、`images.figures`，再执行：

```bash
wewrite run step visual completed
```

只有提示词时同样标 completed，并明确说明未产生费用、没有实际图片。
