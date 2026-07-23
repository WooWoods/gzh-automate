# 配置文件规范与引导流程

## 一、配置文件概述

配置文件存储用户账号信息、内容偏好、过往爆款数据和竞品信息，用于个性化选题推荐和爆款潜力评估。

### 存储位置
- 默认路径：用户工作目录下 `hot-topics-config.yaml`
- 首次运行时自动检测，不存在则引导用户创建

### 文件格式
YAML 格式，支持注释，便于非技术用户编辑。

---

## 二、配置字段完整说明

### 2.1 账号基本信息（account）— 必填

| 字段 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| `name` | string | 是 | 账号名称 | `"科技小王"` |
| `platform` | string | 是 | 主阵地平台 | `"小红书"` |
| `niche` | string | 是 | 赛道/领域 | `"AI工具测评"` |
| `sub_niches` | list[string] | 否 | 细分方向 | `["AI写作工具", "AI绘画工具"]` |
| `tone` | string | 否 | 内容风格描述 | `"专业但不枯燥，带点幽默感"` |
| `target_audience` | object | 否 | 粉丝画像 | 见下方 |

**target_audience 子字段**：

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `age_range` | string | 年龄段 | `"25-40岁"` |
| `gender` | string | 性别分布 | `"男女均衡"` |
| `interests` | list[string] | 兴趣标签 | `["效率工具", "自我提升"]` |
| `pain_points` | list[string] | 痛点 | `["工作重复性高", "想学AI但不知道从哪开始"]` |

### 2.2 内容偏好（content_preferences）— 可选

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `formats` | list[string] | 擅长的内容形式 | `["图文教程", "工具对比", "使用技巧"]` |
| `avg_length` | string | 平均内容长度 | `"800-1500字"` |
| `posting_frequency` | string | 更新频率 | `"日更"` |
| `avoid_topics` | list[string] | 回避话题 | `["政治敏感", "低俗娱乐"]` |

### 2.3 过往爆款数据（past_viral_content）— 可选

用于学习爆款模式、校准评分模型权重。

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `title` | string | 爆款标题 | `"这5个AI工具让我每天省2小时"` |
| `views` | string | 阅读量 | `"10w+"` |
| `likes` | string | 点赞量 | `"5000+"` |
| `platform` | string | 发布平台 | `"小红书"` |
| `topic` | string | 话题分类 | `"AI效率工具"` |
| `why_viral` | string | 爆款原因分析 | `"数字清单型 + 痛点明确 + 工具可立即使用"` |

### 2.4 竞品账号（competitors）— 可选

用于差异化分析，识别竞品已覆盖的角度。

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `name` | string | 竞品账号名 | `"竞品A"` |
| `platform` | string | 所在平台 | `"小红书"` |
| `strength` | string | 竞品优势 | `"工具测评详细"` |
| `weakness` | string | 竞品劣势 | `"更新慢，缺乏个人观点"` |

### 2.5 报告设置（report_settings）— 可选

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `output_dir` | string | `"./hot-topics-reports"` | 报告输出目录 |
| `max_topics` | integer | `10` | 每次报告最大选题数 |
| `min_viral_score` | integer | `70` | 最低收录分数（B级以上） |
| `include_suggestions` | boolean | `true` | 是否包含创作建议 |
| `language` | string | `"zh-CN"` | 报告语言 |

---

## 三、完整配置文件示例

```yaml
# ============================================
# 行业热点选题追踪 - 账号配置文件
# ============================================

# 账号基本信息
account:
  name: "科技小王"
  platform: "小红书"
  niche: "AI工具测评"
  sub_niches:
    - "AI写作工具"
    - "AI绘画工具"
    - "AI编程助手"
  tone: "专业但不枯燥，带点幽默感"
  target_audience:
    age_range: "25-40岁"
    gender: "男女均衡"
    interests:
      - "效率工具"
      - "自我提升"
      - "科技数码"
    pain_points:
      - "工作重复性高"
      - "想学AI但不知道从哪开始"

# 内容偏好
content_preferences:
  formats:
    - "图文教程"
    - "工具对比"
    - "使用技巧"
  avg_length: "800-1500字"
  posting_frequency: "日更"
  avoid_topics:
    - "政治敏感"
    - "低俗娱乐"

# 过往爆款数据（用于学习爆款模式）
past_viral_content:
  - title: "这5个AI工具让我每天省2小时"
    views: "10w+"
    likes: "5000+"
    platform: "小红书"
    topic: "AI效率工具"
    why_viral: "数字清单型 + 痛点明确 + 工具可立即使用"
  - title: "ChatGPT和Claude到底怎么选？实测对比"
    views: "5w+"
    likes: "3000+"
    platform: "公众号"
    topic: "AI工具对比"
    why_viral: "对比型 + 真实测试数据 + 结论明确"

# 竞品账号（用于差异化分析）
competitors:
  - name: "AI工具评测站"
    platform: "小红书"
    strength: "工具测评详细，覆盖面广"
    weakness: "更新慢，缺乏个人观点"
  - name: "效率达人老李"
    platform: "公众号"
    strength: "深度分析，数据详实"
    weakness: "文章太长，不够接地气"

# 报告设置
report_settings:
  output_dir: "./hot-topics-reports"
  max_topics: 10
  min_viral_score: 70
  include_suggestions: true
  language: "zh-CN"
```

---

## 四、首次配置引导流程

当检测到配置文件不存在时，Skill 按以下流程引导用户填写：

### 第一轮：核心信息（必填，3个问题）

```
检测到这是你第一次使用热点选题追踪，需要简单配置一下你的账号信息。

1. 你的账号名称是什么？
2. 你的主阵地是哪个平台？（小红书/抖音/公众号/B站/知乎/头条/其他）
3. 你的内容赛道/领域是什么？（如：AI工具测评、美食探店、职场干货...）
```

### 第二轮：详细信息（可选，2-3个问题）

```
好的，已记录。接下来几个问题可以帮助我更精准地推荐选题（可以直接跳过）：

4. 你的内容风格是怎样的？（如：专业严谨/轻松幽默/干货直给/故事化...）
5. 你的目标粉丝群体是？（年龄段、兴趣方向、核心痛点）
6. 你主要做什么形式的内容？（图文/视频/短视频/长视频...）
```

### 第三轮：高级信息（可选）

```
最后，以下信息可以进一步提升推荐质量（可以稍后在配置文件中补充）：

7. 有没有过往的爆款内容？（提供标题和大概数据即可）
8. 有没有关注或对标的竞品账号？
9. 有没有需要回避的话题类型？
```

### 配置生成

引导完成后，自动生成配置文件并保存到用户工作目录。同时告知用户：
- 配置文件路径，可随时手动编辑
- 如需修改，直接编辑 YAML 文件或重新运行配置引导

---

## 五、配置验证规则

加载配置文件时执行以下验证：

| 验证项 | 规则 | 失败处理 |
|--------|------|---------|
| 文件存在性 | 配置文件必须存在 | 触发首次引导流程 |
| YAML 格式 | 必须是合法 YAML | 提示格式错误，提供示例 |
| account.name | 非空字符串 | 使用默认值 "我的账号" |
| account.platform | 非空字符串 | 使用默认值 "未指定" |
| account.niche | 非空字符串 | 使用默认值 "通用" |
| report_settings.max_topics | 1-50 的整数 | 使用默认值 10 |
| report_settings.min_viral_score | 0-100 的整数 | 使用默认值 70 |
