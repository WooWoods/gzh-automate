# 各平台热点接口文档与降级策略

## 一、数据抓取三级降级策略

抓取热点数据时，按以下优先级依次尝试：

```
Level 1：统一热榜 API（快速、稳定、结构化）
    ↓ 失败
Level 2：各平台独立接口（直接、数据最新）
    ↓ 失败
Level 3：WebSearch 搜索（兜底、覆盖面广）
```

---

## 二、Level 1：统一热榜 API

### 接口信息
- **URL**：`https://60s.viki.moe/v2/{platform}`
- **方法**：GET
- **返回格式**：JSON
- **无需认证**

### 支持的平台参数

| platform 参数 | 平台 | 返回字段 |
|---------------|------|---------|
| `weibo` | 微博热搜 | 排名、标题、热度值 |
| `douyin` | 抖音热点 | 排名、标题、热度值 |
| `baidu` | 百度热搜 | 排名、标题、热度值 |
| `zhihu` | 知乎热榜 | 排名、标题、热度值 |
| `bilibili` | B站热门 | 排名、标题、播放量 |
| `toutiao` | 今日头条 | 排名、标题、热度值 |
| `douban` | 豆瓣热议 | 排名、标题、讨论量 |
| `thepaper` | 澎湃新闻 | 排名、标题、热度值 |
| `36kr` | 36氪 | 排名、标题、热度值 |
| `ithome` | IT之家 | 排名、标题、热度值 |

### 不支持的平台（需降级到 Level 2/3）
- **小红书**：无稳定公开接口
- **微信公众号**：封闭生态，无公开接口

### 响应示例
```json
{
  "code": 200,
  "data": [
    {
      "id": 1,
      "title": "话题标题",
      "hot": "1234567",
      "url": "https://..."
    }
  ],
  "timestamp": 1716000000
}
```

---

## 三、Level 2：各平台独立接口

### 3.1 微博热搜

| 项目 | 说明 |
|------|------|
| URL | `https://weibo.com/ajax/side/hotSearch` |
| 方法 | GET |
| 请求头 | `User-Agent: Mozilla/5.0`, `Referer: https://weibo.com/` |
| 限流 | 约 5次/分钟 |
| 关键字段 | `word`(标题)、`num`(热度值)、`label_name`(标签) |

### 3.2 抖音热点

| 项目 | 说明 |
|------|------|
| URL | `https://www.douyin.com/aweme/v1/web/hot/search/list/` |
| 方法 | GET |
| 请求头 | 需模拟浏览器完整请求头 |
| 关键字段 | `word`(标题)、`hot_value`(热度值) |

### 3.3 知乎热榜

| 项目 | 说明 |
|------|------|
| URL | `https://www.zhihu.com/api/v3/feed/topstory/hot-list-web` |
| 方法 | GET |
| 请求头 | 标准 User-Agent |
| 关键字段 | `target.title`(标题)、`detail_text`(热度描述) |

### 3.4 百度热搜

| 项目 | 说明 |
|------|------|
| URL | `https://top.baidu.com/api/board?platform=wise&tab=realtime` |
| 方法 | GET |
| 关键字段 | `word`(标题)、`desc`(描述) |

### 3.5 B站热门

| 项目 | 说明 |
|------|------|
| URL | `https://api.bilibili.com/x/web-interface/popular?ps=20&pn=1` |
| 方法 | GET |
| 关键字段 | `title`(标题)、`play`(播放量)、`like`(点赞)、`reply`(评论) |

### 3.6 今日头条

| 项目 | 说明 |
|------|------|
| URL | `https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc` |
| 方法 | GET |
| 关键字段 | `Title`(标题)、`HotValue`(热度值) |

---

## 四、Level 3：WebSearch 降级搜索

当 API 接口均不可用时，使用 WebSearch 工具进行搜索。

### 搜索模板

| 平台 | 搜索关键词 |
|------|-----------|
| 微博 | `"{日期} 微博热搜榜"` 或 `"微博热搜 今日"` |
| 抖音 | `"{日期} 抖音热点榜"` 或 `"抖音热搜 今天"` |
| 小红书 | `"{赛道} 小红书 热门话题 爆款"` 或 `"小红书 {关键词} 热门笔记"` |
| 公众号 | `"{赛道} 微信公众号 热门文章 10w+"` 或 `"公众号 {关键词} 爆文"` |
| 知乎 | `"知乎热榜 今日"` |
| 百度 | `"百度热搜榜 今日"` |
| B站 | `"B站热门 今日"` 或 `"bilibili 热门视频"` |
| 头条 | `"今日头条 热榜"` |

### 搜索结果提取规则
- 从搜索结果中提取话题标题和热度描述
- 标注数据来源为"WebSearch 间接获取"
- 可信度标记为"中"（低于直接 API 获取的"高"）

---

## 五、标准化数据格式

所有平台的数据最终统一为以下 JSON 格式：

```json
{
  "topic_id": "wb_001",
  "title": "话题标题",
  "platform": "weibo",
  "platform_name": "微博",
  "heat_value": 1234567,
  "heat_display": "123.4万",
  "rank": 1,
  "category": "社会",
  "url": "https://...",
  "fetch_time": "2025-05-24T10:00:00+08:00",
  "data_source": "api",
  "data_reliability": "high",
  "extra": {
    "discussion_count": "5.2万",
    "label": "热"
  }
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `topic_id` | string | 唯一标识，格式：`{平台缩写}_{序号}` |
| `title` | string | 话题标题 |
| `platform` | string | 平台英文标识 |
| `platform_name` | string | 平台中文名称 |
| `heat_value` | number | 热度数值（标准化后的数值） |
| `heat_display` | string | 热度展示文本 |
| `rank` | integer | 在该平台热榜中的排名 |
| `category` | string | 话题分类（如有） |
| `url` | string | 话题链接 |
| `fetch_time` | string | 数据抓取时间（ISO 8601） |
| `data_source` | string | 数据来源：`api`/`web_search` |
| `data_reliability` | string | 数据可信度：`high`/`medium`/`low` |
| `extra` | object | 平台特有字段 |

### 平台缩写映射

| 平台 | 缩写 |
|------|------|
| 微博 | `wb` |
| 抖音 | `dy` |
| 小红书 | `xhs` |
| 知乎 | `zh` |
| 百度 | `bd` |
| B站 | `bili` |
| 头条 | `tt` |
| 公众号 | `wx` |

---

## 六、错误处理规则

| 错误类型 | 处理方式 |
|---------|---------|
| API 超时（>10秒） | 降级到下一级 |
| API 返回非 200 | 记录错误，降级到下一级 |
| API 返回空数据 | 标注"该平台暂无数据"，继续其他平台 |
| WebSearch 无结果 | 标注"该平台数据获取失败" |
| 所有方式均失败 | 在报告中标注该平台数据缺失，不阻断整体流程 |
