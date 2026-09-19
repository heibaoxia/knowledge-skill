# knowledge-skill

给人用，也给 agent 用的一份 Skill：**怎么用 `knowledge` 命令查自己的资料室**。

## 这是什么

- **本仓库 = 一份 Skill**，只有文档：`SKILL.md`。没有引擎代码，没有书，没有笔记，没有密钥。
- **引擎在另一个仓库**：[heibaoxia/knowledge-mcp](https://github.com/heibaoxia/knowledge-mcp)，装出来的命令叫 `knowledge`。
- 两者关系：本 Skill 是入口和规矩，`knowledge` 命令是干活的闸门。装不装引擎由用时决定，不是装 Skill 时就去联网。

## 装 Skill

放进你的 skills 目录（Claude Code / Codex / 任何读 `SKILL.md` 的 agent），保持目录名是 `knowledge`：

```bash
git clone https://github.com/heibaoxia/knowledge-skill
# 放到 <skills-root>/knowledge/，确保路径是 <skills-root>/knowledge/SKILL.md
```

## 装引擎（本 Skill 会带你做）

```bash
git clone https://github.com/heibaoxia/knowledge-mcp
cd knowledge-mcp
pip install -e ./mcp
export KNOWLEDGE_ROOT=/path/to/资料室
```

`KNOWLEDGE_ROOT` 指知识库根目录；`knowledge init` 可以先把目录骨架建好。细节见 `SKILL.md` 的「先看有没有闸门」。

## 自己用也是这份

给 agent 的 load 说明和给人看的用法是同一份 `SKILL.md` —— 不另维护一份「人类版」，免得两边说法漂移。改规矩就改 `SKILL.md`。

## 许可

MIT，见 `LICENSE`。引擎（knowledge-mcp）自己有自己的许可证。
