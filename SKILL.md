---
name: knowledge
description: Use when the user explicitly asks to use a local knowledge library or 资料室, search ingested books, ingest PDF/EPUB, read a library source, write a library note, or inspect the library. Use this Skill's local CLI bootstrap; do not configure or require MCP, and do not open 资料/ and dump full text.
---

# Knowledge Skill

这份 Skill 让 agent 通过本地 `knowledge` CLI 使用用户自己的资料室。它不包含书、笔记、密钥或知识库内容。

## 通道和触发

- 分享物是这个 Skill 目录，不是 MCP 配置。朋友不需要为使用本 Skill 安装、暴露或配置 MCP 工具。
- 本 Skill 固定走本地 CLI。即使 Harness 同时提供 Knowledge MCP，也不要为本 Skill 修改 MCP 配置或混用两套通道。
- 只有用户明确要求使用资料室、知识库、库中的书、入库、检索、阅读或写笔记时才触发；普通聊天不要开资料室。
- Skill 被 Harness 加载，不等于 CLI 引擎已经安装。首次明确使用时，先完成“首次使用”流程，再执行资料操作。

## 首次使用

不要要求用户先理解 venv、PATH 或 `KNOWLEDGE_ROOT`。找到当前 Skill 目录中的 `bootstrap.py`，使用它完成检查和安装。不同 Harness 的 Skill 根目录不同，所以调用脚本时使用当前 Skill 目录的绝对路径；不要假设当前工作目录就是 Skill 目录。

首次安装前先告诉用户：将联网下载引擎和 Python 依赖，并写入用户目录下的隔离环境；获得同意后再执行。Node.js 不是依赖，Python 需要 3.11 或更高版本。

Windows PowerShell：

```powershell
py -3 "<skill-dir>\bootstrap.py" ensure
```

如果没有 `py`，但 `python --version` 至少为 3.11：

```powershell
python "<skill-dir>\bootstrap.py" ensure
```

macOS/Linux：

```bash
python3 "<skill-dir>/bootstrap.py" ensure
```

把 `<skill-dir>` 替换成当前 Skill 目录的绝对路径。bootstrap 会：

1. 检查 Python 版本；
2. 优先使用 Git，否则用 Python 标准库下载 GitHub ZIP；
3. 在用户目录的 `.knowledge/engine` 创建隔离 venv；
4. 安装引擎及依赖，默认 PyPI 失败时重试清华镜像；
5. 用 `python -m knowledge_mcp.cli --help` 验证 CLI。

引擎目录可由 `KNOWLEDGE_ENGINE_DIR` 覆盖。bootstrap 不修改 PATH、不使用 `setx`，也不会递归删除用户目录。

只认 bootstrap 的退出状态：

- `0`：CLI 已就绪；
- `10`：Python 低于 3.11；
- `20`：GitHub、PyPI 或镜像不可用；
- `30`：没有提供知识库绝对路径；
- `40`：权限、引擎目录或 CLI 验证失败。

安装失败时报告具体状态和错误并停止，不要改为直接翻 `资料/`，也不要声称已经查过库。

## 确认知识库路径

不要猜用户的资料室路径，也不要因为当前目录有 `资料/` 就把它当成知识库。向用户确认一个绝对路径：

- 已有知识库：确认它的绝对路径；
- 新建知识库：确认要创建的绝对路径。可建议 Windows 的 `%USERPROFILE%\资料室` 或 macOS/Linux 的 `$HOME/资料室`，但必须让用户确认。

每次 CLI 调用都通过 bootstrap 显式传入路径，因此不依赖上一条工具调用留下的 shell、当前目录或环境变量。Harness 经常为每次工具调用启动新的 shell，这一点不能假设。

已有知识库先扫描：

```powershell
py -3 "<skill-dir>\bootstrap.py" run --library "C:\Users\someone\资料室" -- lint scan
```

新建知识库时：

```powershell
py -3 "<skill-dir>\bootstrap.py" run --library "C:\Users\someone\资料室" -- init
py -3 "<skill-dir>\bootstrap.py" run --library "C:\Users\someone\资料室" -- lint scan
```

macOS/Linux 对应写法：

```bash
python3 "<skill-dir>/bootstrap.py" run --library "$HOME/资料室" -- lint scan
```

`lint scan` 必须确认实际扫描的是用户指定的路径。扫描出 0 本时先核对路径，不能直接告诉用户“库里没有”。已有库不要运行 `init`。

## 常用操作

bootstrap 会把 `--` 后面的参数原样交给本地 `knowledge` CLI：

| 命令 | 用途 |
| --- | --- |
| `search <一句话>` | 只返回路标，先搜再读 |
| `read 书/<slug>/<章>` | 按检索结果点名读正文 |
| `ingest` | 把 `原始资料/` 中的 PDF/EPUB 转成书 |
| `ingest <路径...>` | 只转指定文件 |
| `lint scan` | 查看在架内容和问题 |
| `lint apply --plan '[...]'` | 更新地图、净化笔记 |
| `note preview\|verify\|create\|update` | 按流程写笔记 |
| `inspect` | 查看最近调用和失败记录 |

## 检索：先 search，再 read

`search` 只返回路标，不返回正文，所以永远不要把路标当答案。拿到书、章节的身份后，再点名 `read`。一次最多读 5 个块，单块上限 8000 字，整次上限 24000 字；超长章的后半用 `章名#2`。够答就停，不要按目录读完整个库，也不要直接打开 `资料/` 灌全文。

## 入库：骨架不算入完

`ingest` 后必须继续加厚地图：补上读者会怎么问，以及至少 3 个别名，然后走 `lint apply` 更新 `书/<slug>/地图`。只写骨架就报“入完了”是不完整的。

## 写笔记

严格按 `preview` → `verify` → `create` / `update`。`verify` 判定“相符”前，必须先用 `read` 读过依据。笔记写入用户的知识库，不要写进 Skill 目录或分享物。

## 数据和禁止事项

如果环境配置了 `KNOWLEDGE_EMBED_KEY`，引擎的向量检索可能会把查询和相关内容发送给对应的第三方服务；没有该配置时使用本地检索路径。私密资料使用前先确认这符合用户预期。

- 不要把路标当正文，或编造库里没有的内容。
- CLI 不可用时不要直接翻 `资料/` 代替 CLI。
- 不经 `lint apply` 直接改 `资料/` 里的书。
- 不要把用户的书、笔记、路径或库内容放进 Skill、提交或分享给别人。
