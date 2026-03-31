# 微信公众号文章爬虫与总结系统

## 项目简介
基于CSV文件中的微信公众号链接，批量提取近1个月内的文章内容，并按公众号分组生成**完整详细**的内容总结报告。

**核心特点**：
- ✅ **完整信息提取** - 提取文章所有段落，不遗漏任何内容
- ✅ **智能内容总结** - 使用AI提炼关键信息、数据、观点、技术细节
- ✅ **按公众号分组** - 自动识别公众号并分类管理
- ✅ **时间范围过滤** - 支持按天数过滤文章（默认30天）
- ✅ **多格式输出** - 支持Markdown、JSON格式报告

## 快速开始

### 1. 安装依赖
```bash
cd ~/Downloads/wechat-article-crawler
pip install -r requirements.txt
```

### 2. 配置参数
编辑 `config.yaml` 文件：

```yaml
# 修改CSV文件路径（如已正确设置则跳过）
csv_file: "/Users/mac389/Desktop/资产backup-行业资讯.csv"

# AI总结配置（推荐启用）
ai_summary:
  enabled: true  # 是否启用AI总结
  api_key: "your-api-key-here"  # 填入你的API密钥
  base_url: "https://api.openai.com/v1"  # API地址
  model: "gpt-4o"  # 模型名称
```

**注意**：
- 如果不配置API，系统将生成简单的文章列表总结
- 配置AI后可生成深度分析报告，包含关键信息提取和趋势分析

### 3. 运行程序
```bash
# 方式1: 完整流程（推荐）
python main.py --mode full

# 方式2: 仅爬取文章（不生成总结）
python main.py --mode crawl
```

## 输出结果

运行完成后，将在以下位置生成文件：

```
wechat-article-crawler/
├── data/
│   ├── raw/
│   │   └── articles.json                    # 原始文章数据（所有字段）
│   └── processed/
│       └── articles_by_account.json         # 按公众号分组的文章
├── output/
│   ├── summary_report.md                    # ⭐ 完整总结报告（推荐查看）
│   ├── summaries.json                       # 总结数据JSON格式
│   └── index.md                             # 索引文件
└── logs/
    ├── crawler.log                          # 爬虫日志
    └── main.log                             # 主程序日志
```

### 主要文件说明

#### 1. `output/summary_report.md` - 完整总结报告
这是最重要的输出文件，包含：
- 📊 整体概览（公众号数量、文章总数）
- 📈 公众号文章排行榜
- 📝 每个公众号的详细总结：
  - 核心内容总结（主题、关键信息、技术细节）
  - 关键洞察与趋势
  - 重点文章推荐
  - 完整文章列表（带链接）

#### 2. `data/raw/articles.json` - 原始文章数据
包含每篇文章的完整信息：
```json
{
  "url": "文章链接",
  "title": "文章标题",
  "author": "作者",
  "account_name": "公众号名称",
  "publish_time": "发布时间",
  "content": "完整正文内容",
  "digest": "文章摘要",
  "article_id": "文章唯一ID",
  "biz_id": "公众号BIZ ID"
}
```

## 功能特点

### 1. 完整内容提取
- 提取文章所有段落、标题、列表
- 保留文章结构和格式
- **确保不遗漏任何关键信息**

### 2. 智能总结（启用AI时）
系统会为每个公众号生成包含以下内容的总结：
- 📊 公众号概览（发文频率、内容方向）
- 🔑 核心内容总结（按主题分类）
- 💡 关键洞察与趋势
- 📌 重点文章推荐
- 🎯 整体总结

**总结时会特别关注**：
- ✓ 重要数据和统计
- ✓ 技术细节和创新点
- ✓ 产品/工具/方案名称
- ✓ 行业趋势和洞察
- ✓ 关键观点和结论

### 3. 防封策略
- 请求间隔3秒（可配置）
- 随机User-Agent
- 失败自动重试（最多3次）
- 超时保护机制

## 配置说明

### config.yaml 主要参数

```yaml
# 时间范围
days_range: 30  # 只抓取近30天的文章

# 爬虫设置
crawler:
  request_interval: 3  # 请求间隔（秒）- 建议不低于3秒
  timeout: 30          # 请求超时（秒）
  max_retries: 3       # 最大重试次数
  retry_delay: 5       # 重试延迟（秒）

# AI总结设置
ai_summary:
  enabled: true               # 是否启用AI总结
  api_key: "sk-xxx"          # API密钥
  base_url: "https://..."    # API地址（支持OpenAI兼容接口）
  model: "gpt-4o"            # 模型（推荐gpt-4o或gpt-4-turbo）
  max_tokens: 4000           # 单次总结最大token数
  temperature: 0.3           # 生成温度（0-1，越低越准确）
```

## 使用示例

### 示例1: 使用默认配置
```bash
cd ~/Downloads/wechat-article-crawler
python main.py --mode full
```

### 示例2: 使用自定义配置文件
```bash
python main.py --mode full --config my_config.yaml
```

### 示例3: 分步执行
```bash
# 步骤1: 先爬取文章
python main.py --mode crawl

# 步骤2: 手动查看 data/raw/articles.json

# 步骤3: 生成总结（待实现）
python main.py --mode summarize
```

## 常见问题

### Q1: 为什么有些文章抓取失败？
**可能原因**：
- 文章已删除或设置为仅粉丝可见
- 请求频率过高被临时限制
- 网络连接问题

**解决方案**：
- 检查日志文件 `logs/crawler.log`
- 增加请求间隔时间（修改config.yaml中的request_interval）
- 稍后重试

### Q2: CSV文件格式要求？
系统会自动查找包含以下关键词的列：
- `source`
- `url`
- `链接`

或者自动扫描所有列，识别微信公众号链接。

### Q3: 如何配置AI总结？
支持OpenAI及兼容接口：

**OpenAI官方**:
```yaml
api_key: "sk-xxxxx"
base_url: "https://api.openai.com/v1"
model: "gpt-4o"
```

**国内兼容接口**（示例）:
```yaml
api_key: "your-key"
base_url: "https://api.你的服务.com/v1"
model: "gpt-4o"
```

**本地模型（如Ollama）**:
```yaml
api_key: "ollama"
base_url: "http://localhost:11434/v1"
model: "qwen2.5"
```

### Q4: 不使用AI可以吗？
可以！设置 `ai_summary.enabled: false`，系统会生成：
- 文章列表
- 基本统计
- 按时间排序的文章清单

虽然没有深度总结，但所有原始内容都保存在JSON文件中。

### Q5: 内容总结会遗漏信息吗？
**不会**！系统设计确保：
1. 爬虫阶段：提取文章所有段落和内容
2. 总结阶段：AI会分析完整内容，提取关键信息
3. 如果内容过长（>60k tokens），会分批总结后再汇总
4. 所有原始内容都保存在 `data/raw/articles.json`

## 项目结构

```
wechat-article-crawler/
├── README.md           # 项目说明（本文件）
├── requirements.txt    # 依赖库
├── config.yaml        # 配置文件
├── main.py            # 主程序入口
├── crawler.py         # 爬虫模块
├── parser.py          # 文章解析模块
├── summarizer.py      # AI总结模块
├── utils.py           # 工具函数
├── data/              # 数据目录
│   ├── raw/          # 原始文章数据
│   └── processed/    # 处理后的数据
├── output/            # 输出报告目录
└── logs/              # 日志文件
```

## 技术架构

- **requests** - HTTP请求
- **BeautifulSoup4** - HTML解析
- **pandas** - CSV数据处理
- **openai** - AI接口调用
- **tqdm** - 进度条显示
- **pyyaml** - 配置文件解析

## 注意事项

1. **请求频率**：默认3秒间隔，建议不要修改太小
2. **API成本**：如使用OpenAI API，会产生费用（取决于文章数量）
3. **数据隐私**：请遵守相关法律法规，仅用于学习研究
4. **防封策略**：
   - 不要短时间大量请求
   - 使用代理IP（需自行配置）
   - 分批次执行

## 开发计划

- [ ] 支持从已有数据重新生成总结
- [ ] 添加图片下载功能
- [ ] 支持更多AI接口（Claude、通义千问等）
- [ ] 添加增量更新功能
- [ ] Web可视化界面

## 许可证
MIT License

## 参考项目
- [lukelei2025/wechat-article-claw](https://github.com/lukelei2025/wechat-article-claw)

---

**开始使用**：
```bash
cd ~/Downloads/wechat-article-crawler
pip install -r requirements.txt
python main.py --mode full
```

查看结果：`output/summary_report.md`
