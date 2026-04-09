<div align="center">

# iDeer: 🦌 is all u need

> 「这倒是提醒我了」

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-purple.svg)](https://claude.ai/code)
[![AgentSkills Standard](https://img.shields.io/badge/AgentSkills-Standard-brightgreen.svg)](https://github.com/anthropics/agent-skills)

[English](./README.en.md) · [技术文档](./docs/TECHNICAL.md) · [桌面 Demo](./docs/DESKTOP_DEMO.md)

<img src="./docs/ideer.svg" alt="iDeer Icon" width="360" />

iDeer 解决一个朴素的问题：**你感兴趣的东西散落在五个平台，你没有五倍的时间。**

写一份兴趣画像，剩下的交给鹿。它每天替你盯盘，把值得看的 repo、论文、模型和推文，蒸馏成你能 5 分钟读完的情报。

## 它能产出什么

| 产出                 | 说明                           | 示例路径                           |
| -------------------- | ------------------------------ | ---------------------------------- |
| **📰 日报**           | 每个源的精选推荐 + AI 摘要     | `history/<source>/<date>/`         |
| **📋 跨源简报**       | 打通五个源的个性化叙事报告     | `history/reports/<date>/report.md` |
| **💡 Research Ideas** | 从当天情报里自动长出的研究灵感 | `history/ideas/<date>/ideas.json`  |

不只是 RSS —— 它会**打分、排序、总结、跨源关联**，最后用邮件把结果投喂给你。

## 数据源

| 源                    | 抓取方式                     | 你能配置的                     |
| --------------------- | ---------------------------- | ------------------------------ |
| **GitHub**            | Trending 页面爬取            | 语言过滤、时间范围、最大数量   |
| **HuggingFace**       | 官方 API (论文 + 模型)       | 内容类型、数量上限             |
| **arXiv**             | 每日新论文列表               | 分类、领域                     |
| **Semantic Scholar**  | 免费 API（WoS 替代，2亿+论文）| 搜索词、年份、领域、数量       |
| **X / Twitter**       | RapidAPI twitter-api45       | 账号列表、自动发现、回溯时间窗 |

> Semantic Scholar 覆盖 arXiv 之外的会议、期刊论文 —— 免费版 Web of Science。
>
> Twitter 源支持**基于画像的账号自动发现** —— 不用手动维护关注列表，鹿会自己去找值得盯的人。

## 快速开始

```bash
# 1. 环境
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# 2. 最少配三项
# MODEL_NAME=    BASE_URL=    API_KEY=
vim .env

# 3. 写你的兴趣画像
vim profiles/description.txt

# 4. 跑一次试试（不发邮件）
python main.py --sources github huggingface arxiv semanticscholar --save --skip_source_emails
```

搞定。去 `history/` 看产出。

## 完整日报机

想要每天自动跑 + 收邮件 + 生成报告和点子？

```bash
# .env 里补上：
SMTP_SERVER=xxx       # 邮件相关
SMTP_PORT=465
SENDER=xxx
RECEIVER=xxx
SENDER_PASSWORD=xxx
X_RAPIDAPI_KEY=xxx    # Twitter（可选）
GENERATE_REPORT=1     # 开启跨源报告
GENERATE_IDEAS=1      # 开启研究灵感

# 一键流水线
bash scripts/run_daily.sh
```

配个 cron，每天早上 8 点自动投喂：

```bash
0 8 * * * /path/to/iDeer/scripts/run_daily.sh >> /var/log/ideer.log 2>&1
```

## 架构

```
你的兴趣画像 + Google Scholar（支持多个）
     ↓
┌─────────┐  ┌──────────────┐  ┌────────┐  ┌─────────────────┐  ┌───────────┐
│ GitHub  │  │ HuggingFace  │  │ arXiv  │  │ Semantic Scholar │  │ X/Twitter │
└────┬────┘  └──────┬───────┘  └───┬────┘  └────────┬────────┘  └─────┬─────┘
     │              │              │                 │                 │
     └──────────────┴──────────────┴────────┬────────┴─────────────────┘
                                            ↓
                                     LLM 评分 + 筛选
                                            ↓
                               ┌────────────┼────────────┐
                               ↓            ↓            ↓
                            📰 日报    📋 跨源简报   💡 Ideas
                               ↓            ↓            ↓
                                      📧 邮件投喂
                                            ↓
                              ┌─────────────────────────────┐
                              │  ⏰ 定时推送（支持仅工作日）  │
                              └─────────────────────────────┘
```

插件化设计 —— 想加新源？继承 `BaseSource`，实现抽象方法，注册到 `SOURCE_REGISTRY`，完事。

## 扩展能力

- **🖥️ Web UI** — 内置 FastAPI 后端 + WebSocket 实时日志，浏览器里跑
- **⏰ 定时推送** — 支持每日 / 仅工作日 / 每周 / 每月，在 Admin 页面配置
- **🖥️ 桌面客户端** — 本地 GUI 体验（见 [Desktop Demo](./docs/DESKTOP_DEMO.md)）
- **🔌 Claude Code Skill** — 支持作为 Claude Code 技能集成
- **🎓 多 Scholar 画像** — 支持同时关联多个 Google Scholar 账户

## FAQ

**Q：支持哪些 LLM？**
A：任何 OpenAI 兼容 API（含本地 Ollama）。

**Q：不想发邮件？**
A：加 `--skip_source_emails`，产出存本地。

**Q：Twitter 必须配吗？**
A：不必。`--sources` 按需选。

**Q：能自定义评分逻辑吗？**
A：重写 `build_eval_prompt()` 和 `parse_eval_response()`，鹿随你调教。

---

<div align="center">


**如果这只鹿帮你省了时间，给它一颗 ⭐**

[![Star History Chart](https://api.star-history.com/svg?repos=LiYu0524/iDeer&type=Date)](https://star-history.com/#LiYu0524/iDeer&Date)

MIT License · Made by [@LiYu0524](https://github.com/LiYu0524)

</div>
