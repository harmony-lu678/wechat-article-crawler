# 快速使用指南

## 🚀 三步开始

### 步骤1: 测试系统（推荐）
```bash
cd ~/Downloads/wechat-article-crawler
python test.py
```
这会爬取一篇测试文章，验证系统是否正常工作。

### 步骤2: 配置AI（可选但推荐）
编辑 `config.yaml` 文件，找到以下部分：

```yaml
ai_summary:
  enabled: true  # 确保为true
  api_key: "your-api-key-here"  # ⬅️ 在这里填入你的API密钥
  base_url: "https://api.openai.com/v1"  # 或其他兼容接口
  model: "gpt-4o"  # 模型名称
```

**如果不配置AI**：
- 系统仍会运行
- 但只生成简单的文章列表，没有深度总结
- 所有原始内容仍会完整保存

### 步骤3: 运行完整爬虫
```bash
# 方式1: 使用快速启动脚本（推荐）
./run.sh

# 方式2: 直接运行Python脚本
python main.py --mode full
```

## 📊 预期结果

### 爬取进度
```
正在爬取: https://mp.weixin.qq.com/s?__biz=...
爬取进度: 1/131 [▓░░░░░░░░░] 0.8%
成功抓取文章: 套壳 Flux 模型年入100万美金？...
```

### 生成的文件

#### 1. 完整总结报告（最重要）
`output/summary_report.md`

内容示例：
```markdown
# 微信公众号文章内容总结报告

## 📊 整体概览
- 公众号数量: 15 个
- 文章总数: 131 篇
- 时间范围: 近 30 天

## 📝 各公众号详细总结

### AI科技评论_MjM5NDQ3ODI3NQ==

**文章数量**: 12 篇

## 📊 公众号概览
该公众号专注于AI技术和产品分析，平均每周发文2-3篇...

## 🔑 核心内容总结

### 主题1: AI图像生成模型
- Flux模型商业化案例：年收入100万美金
- 关键数据：用户量50万+，转化率3.2%
- 技术细节：采用扩散模型架构，支持ControlNet...

### 主题2: ComfyUI更新
- 版本0.3.51新增7大功能
- 重要功能：子图系统、迷你地图、管理器界面优化
...

## 💡 关键洞察与趋势
1. AI图像生成工具商业化进入快速发展期
2. 开源工具生态日益完善...

## 📌 重点文章推荐
1. **套壳 Flux 模型年入100万美金** - 详细分析了...
2. **ComfyUI 0.3.51更新** - 介绍了最新功能...
...
```

#### 2. 原始数据
`data/raw/articles.json`
```json
[
  {
    "url": "https://mp.weixin.qq.com/s?...",
    "title": "套壳 Flux 模型年入100万美金",
    "author": "AI科技评论",
    "account_name": "AI前线",
    "publish_time": "2024-08-24",
    "content": "完整的文章正文内容...",
    "article_id": "MjM5NDQ3ODI3NQ==_2651430654_1",
    "biz_id": "MjM5NDQ3ODI3NQ=="
  }
]
```

## ⚙️ 高级配置

### 调整爬取速度
编辑 `config.yaml`:
```yaml
crawler:
  request_interval: 3  # 改为5秒，更安全但更慢
  timeout: 30          # 超时时间
  max_retries: 3       # 重试次数
```

### 修改时间范围
```yaml
days_range: 30  # 改为60，爬取近2个月的文章
```

### 使用本地AI模型（Ollama）
```yaml
ai_summary:
  enabled: true
  api_key: "ollama"
  base_url: "http://localhost:11434/v1"
  model: "qwen2.5:14b"
```

## 🔍 查看结果

### 使用VSCode/Cursor查看
```bash
code output/summary_report.md
```

### 使用终端查看
```bash
cat output/summary_report.md | less
```

### 查看JSON数据
```bash
python -m json.tool data/raw/articles.json | less
```

## 📈 执行时间估算

- 爬取131篇文章：约 **7-10分钟**（3秒/篇）
- AI总结（15个公众号）：约 **5-8分钟**（视模型速度）
- **总计**：约 **15-20分钟**

## ❓ 常见问题

### Q: 爬取速度太慢？
A: 这是正常的，每篇文章间隔3秒是为了避免被封。**不建议**调快。

### Q: 某些文章爬取失败？
A: 查看日志:
```bash
cat logs/crawler.log | grep "ERROR"
```
常见原因：文章已删除、网络问题、被限制。

### Q: AI总结生成失败？
A: 检查：
1. API密钥是否正确
2. 网络连接是否正常
3. 查看日志: `logs/main.log`

### Q: 想重新生成总结？
A: 暂时需要重新运行完整流程。未来会支持单独生成总结。

## 💡 使用技巧

### 技巧1: 分批处理
如果文章太多，可以先测试小范围：
```python
# 修改 main.py 中的爬取逻辑
urls = self.load_urls_from_csv()[:20]  # 只爬前20篇
```

### 技巧2: 断点续爬
程序会自动跳过已爬取的文章（基于文章ID）。

### 技巧3: 导出Excel
```python
import pandas as pd
import json

with open('data/raw/articles.json', 'r') as f:
    articles = json.load(f)

df = pd.DataFrame(articles)
df.to_excel('articles.xlsx', index=False)
```

## 🎯 下一步

1. ✅ 运行测试脚本验证系统
2. ✅ 配置AI接口（可选）
3. ✅ 运行完整爬虫
4. ✅ 查看总结报告
5. 🎉 根据需要调整配置

---

**遇到问题？**
查看详细文档: `README.md`
查看日志文件: `logs/`
