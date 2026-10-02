# knowledge-skill

给人用，也给 agent 用的一份 Skill：让 agent 通过本地 `knowledge` CLI 使用自己的资料室。

## 先说结论

安装 Skill 后，Harness 可以发现并触发它；但 `knowledge` 引擎不是 Harness 自带的，所以第一次明确使用资料室时仍需要一次初始化。仓库附带的 `bootstrap.py` 会自动完成可自动化的部分：检查 Python、下载引擎源码、创建隔离 venv、安装依赖、验证 CLI，并在每次调用时使用绝对路径。

用户只需要明确两件事：

- 允许首次使用时联网下载引擎和 Python 依赖；
- 告诉 agent 已有知识库的绝对路径，或确认要新建的路径。

这条路径不需要 Node.js，不需要 MCP 配置，也不会默认修改 PATH 或永久写入环境变量。

## 这是什么

- **本仓库是一份 Skill**，核心文件是 `SKILL.md` 和 `bootstrap.py`；不包含引擎代码、书、笔记或密钥。
- **引擎在另一个仓库**：[heibaoxia/knowledge-mcp](https://github.com/heibaoxia/knowledge-mcp)。bootstrap 会在用户目录下准备它。
- **分享方式是 Skill，不是 MCP**：朋友不需要安装、暴露或配置 `kb_*` MCP 工具。
- Python 需要 3.11 或更高版本。Node.js 不参与本 Skill。没有 Git 时，bootstrap 会回退到 GitHub ZIP 下载。

## 安装 Skill

如果 Harness 提供导入/安装 Skill 的入口，直接导入本仓库。手动安装时，把仓库内容放进 Harness 会读取的 skills 根目录下的 `knowledge` 目录，并确认下面的文件直接存在：

```text
<skills-root>/knowledge/SKILL.md
<skills-root>/knowledge/bootstrap.py
```

不同 Harness 的 skills 根目录不同，不能假设所有产品都使用同一个路径。Windows PowerShell 的一个常见示例是：

```powershell
$SkillsRoot = Join-Path $env:USERPROFILE ".agents\skills"
$SkillDir = Join-Path $SkillsRoot "knowledge"
if (Test-Path -LiteralPath $SkillDir) {
  throw "目标目录已存在，请先确认它就是要更新的 knowledge Skill：$SkillDir"
}
New-Item -ItemType Directory -Force $SkillsRoot | Out-Null
git clone https://github.com/heibaoxia/knowledge-skill $SkillDir
```

这只是目录示例，不是所有 Harness 的官方路径。没有 Git 时，下载本仓库 ZIP，并把内容解压到名为 `knowledge` 的目录；最终必须是 `$SkillDir\SKILL.md` 和 `$SkillDir\bootstrap.py`，不要让文件多套一层 `knowledge-skill` 目录。已有安装请直接更新原目录，不要在它里面再次 clone。安装后重新开始一轮对话，并让 agent 确认它已经加载 `knowledge` Skill。

## 首次使用

用户明确说“查资料室”“检索”“入库”或类似意图后，agent 应先调用当前 Skill 目录中的 `bootstrap.py`。手动执行时，在 Skill 目录中运行：

Windows PowerShell：

```powershell
py -3 .\bootstrap.py ensure
```

如果没有 `py`，但 `python --version` 至少为 3.11：

```powershell
python .\bootstrap.py ensure
```

macOS/Linux：

```bash
python3 ./bootstrap.py ensure
```

首次执行会：

1. 检查 Python 版本；
2. 优先使用 Git，否则下载 GitHub ZIP；
3. 在 `~/.knowledge/engine` 创建隔离 venv；
4. 安装引擎及其依赖；
5. 用 `python -m knowledge_mcp.cli --help` 验证入口。

默认 PyPI 源失败时会自动重试清华镜像。安装失败会报告状态并停止，不会绕过 CLI 直接翻资料文件。

## 指定知识库并运行

每次调用都显式传入知识库绝对路径，避免 Harness 的新 shell 丢失环境变量，也避免 CLI 静默猜错目录。命令后的 `--` 用来分隔 bootstrap 参数和 `knowledge` 参数。

已有知识库先扫描：

```powershell
py -3 .\bootstrap.py run --library "$env:USERPROFILE\资料室" -- lint scan
```

新建知识库时：

```powershell
py -3 .\bootstrap.py run --library "$env:USERPROFILE\资料室" -- init
py -3 .\bootstrap.py run --library "$env:USERPROFILE\资料室" -- lint scan
```

macOS/Linux：

```bash
python3 ./bootstrap.py run --library "$HOME/资料室" -- lint scan
python3 ./bootstrap.py run --library "$HOME/资料室" -- search "你的问题"
```

`lint scan` 必须确认实际扫描的是用户指定的路径。扫描出 0 本时，先核对路径，不要直接向用户报告“库里没有”。已有库不要运行 `init`。

## 常用操作

bootstrap 会把下面的参数原样交给 `knowledge` CLI：

| 操作 | 用途 |
| --- | --- |
| `search <一句话>` | 只返回路标，先搜再读 |
| `read 书/<slug>/<章>` | 按检索结果点名读正文 |
| `ingest` | 把 `原始资料/` 中的 PDF/EPUB 转成书 |
| `ingest <路径...>` | 只转指定文件 |
| `lint scan` | 查看在架内容和问题 |
| `lint apply --plan '[...]'` | 更新地图、净化笔记 |
| `note preview\|verify\|create\|update` | 按流程写笔记 |
| `inspect` | 查看最近调用和失败记录 |

完整的触发规则、先搜索后阅读、入库地图加厚和笔记求证流程见 [SKILL.md](SKILL.md)。

## 状态码

`bootstrap.py` 的错误状态供 agent 判断：

- `0`：已就绪；
- `10`：Python 版本低于 3.11；
- `20`：网络或依赖安装失败；
- `30`：尚未提供知识库绝对路径；
- `40`：权限、引擎目录、CLI 验证失败或 bootstrap 参数错误。

`run` 成功启动后，后面的退出码由 `knowledge` 子命令原样返回；这不是 bootstrap 的安装状态码。

引擎目录可用 `KNOWLEDGE_ENGINE_DIR` 覆盖，默认是用户目录下的 `.knowledge/engine`。bootstrap 不会递归删除用户目录，也不会把资料室写入 Skill 仓库。

## 数据边界

Skill 和 bootstrap 不会把用户的书、笔记或资料室打进分享物。若用户环境配置了 `KNOWLEDGE_EMBED_KEY`，引擎的向量检索可能会把查询和相关内容发送给对应的第三方服务；没有该配置时使用本地检索路径。私密资料使用前应先确认这个配置是否符合用户预期。

## 许可

MIT，见 [LICENSE](LICENSE)。引擎 `knowledge-mcp` 自己有自己的许可证。
