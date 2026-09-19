---
name: knowledge
description: Use when the user asks to use their local knowledge library, 资料室, 知识库, search books they ingested, ingest PDF/EPUB, or list what is in the library. Prefer the knowledge CLI. Do not open 资料/ and dump full text.
---

# Knowledge Skill

给人用，也给 agent 用。这份 Skill 只是入口和规矩；**真正的活儿由 `knowledge` 命令干**，知识库本身留在用户自己的目录里，不进本仓库。

## 入口在哪

- 入口 = 本 Skill（你正在读的这份）。
- 闸门 = 命令 `knowledge`。所有检索、入库、写笔记都走它，不要绕过它去翻文件。
- 同一套引擎也有 MCP 前端（`kb_*` 工具），和命令行二选一，别同时用两套。

## 先看有没有闸门

```bash
command -v knowledge
```

**有** → 直接往下用。

**没有** → 先装引擎（不要假装查过库）。需要 Python 3.11+：

```bash
git clone https://github.com/heibaoxia/knowledge-mcp.git
cd knowledge-mcp
python -m venv .venv
.venv/Scripts/python -m pip install -e ./mcp    # Windows
.venv/bin/python     -m pip install -e ./mcp    # macOS / Linux
```

（PyPI 上的包名是 `ziliaoshi`，但命令行叫 `knowledge`；从 `mcp/` 这个子目录装才有它。）

装完必须设 `KNOWLEDGE_ROOT`，指向用户的知识库根目录：

```bash
export KNOWLEDGE_ROOT=/path/to/资料室      # 目录里有 原始资料/、资料/书/、资料/笔记/
```

**别跳过这一步**：`KNOWLEDGE_ROOT` 没设时它不会报错，而是悄悄按当前目录去找库 —— 你可能扫了个空目录，然后对着用户说「库里没有」。宁可先 `knowledge lint scan` 确认扫的是哪个库。

首次使用可以 `knowledge init` 把目录骨架建出来。这只装一次，不是每次对话都去联网。

## 何时开门

用户点名知识库 / 资料室 / 查库里的书 / 往库里丢书。没点名：当普通聊天。

## 常用命令

在知识库目录里执行，或先 `export KNOWLEDGE_ROOT=...`：

| 命令 | 干什么 |
| --- | --- |
| `knowledge init` | 建知识库目录骨架（第一次用） |
| `knowledge search <一句话>` | 只回路标，无正文。**先搜再读** |
| `knowledge read 书/<slug>/<章>` | 读正文，一次可点名多个 |
| `knowledge ingest` | 把收件箱 `原始资料/` 里的 PDF/EPUB 转成书 |
| `knowledge ingest <路径...>` | 只转点名的那些文件 |
| `knowledge lint scan` | 报「在架」（库里有什么）+ 问题 |
| `knowledge note preview\|verify\|create\|update [--file note.md]` | 写笔记（`--file` 省略 = 从 stdin 读） |
| `knowledge lint apply --plan '[...]'` | 按计划改库（改地图、净化笔记） |
| `knowledge inspect` | 自检：最近调用和失败记录 |

## 检索：先 search，再 read

`knowledge search` 只给**路标**（哪本书、哪一章可能相关），不返回正文 —— 所以永远不要拿路标当答案。

拿到身份后再点名读：

```bash
knowledge read 书/<slug>/<章>
```

一次最多点 5 块，单块上限 8000 字、整次 24000 字，超了会被截断。超长章开头之外的内容用 `章名#2` 取后半。

**够答就停**：不要按目录把每章都读一遍，也不要打开 `资料/` 灌全文。

## 入库：骨架不算入完

`knowledge ingest` 的回报里带着流程：代码已经做了切块和骨架地图。**你必须再做加厚** —— 读者会怎么问 + 至少 3 个别名 —— 然后走 `knowledge lint apply` 更新 `书/<slug>/地图`。

只写了骨架就报「入完了」＝ 没入完。

## 写笔记

`preview` → `verify` → `create` / `update`，三步走。

`verify` 判「相符」之前，必须先用 `knowledge read` 读过依据。笔记和书共用同一套检索，只是入库时多求证一层。

## 不要做

- 没点名就开资料室
- 把路标当正文，或编造库里没有的内容
- 入库只写骨架就报入完
- 不经 `lint apply` 直接改 `资料/` 里的书
- 为了「只留一本」把相关的第二本书藏起来
