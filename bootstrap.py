"""Prepare and run the local knowledge CLI without relying on shell state."""

from __future__ import annotations

import argparse
import http.client
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ENGINE_REPOSITORY = "https://github.com/heibaoxia/knowledge-mcp.git"
ENGINE_ZIP_BASE = "https://github.com/heibaoxia/knowledge-mcp/archive/refs/heads/{}.zip"
MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"
PROBE_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 120
INSTALL_TIMEOUT = 900


class BootstrapError(Exception):
    def __init__(self, code: int, status: str, message: str):
        super().__init__(message)
        self.code = code
        self.status = status
        self.message = message


def configure_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


def default_engine_dir() -> Path:
    configured = os.environ.get("KNOWLEDGE_ENGINE_DIR")
    return Path(configured).expanduser() if configured else Path.home() / ".knowledge" / "engine"


def venv_python(engine_dir: Path) -> Path:
    if os.name == "nt":
        return engine_dir / ".venv" / "Scripts" / "python.exe"
    return engine_dir / ".venv" / "bin" / "python"


def cli_module_command(engine_dir: Path) -> list[str]:
    return [str(venv_python(engine_dir)), "-m", "knowledge_mcp.cli"]


def command_env(root: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    if root is not None:
        env["KNOWLEDGE_ROOT"] = str(root)
    return env


def probe_command(command: list[str], cwd: Path | None = None) -> bool:
    try:
        result = subprocess.run(
            [*command, "--help"],
            cwd=cwd,
            env=command_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=PROBE_TIMEOUT,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False
    help_text = result.stdout.lower()
    return result.returncode == 0 and all(word in help_text for word in ("search", "ingest", "lint"))


def find_working_cli(engine_dir: Path, allow_global: bool) -> list[str] | None:
    engine_python = venv_python(engine_dir)
    if engine_python.is_file():
        module_command = cli_module_command(engine_dir)
        if probe_command(module_command, engine_dir):
            return module_command
    if allow_global:
        global_cli = shutil.which("knowledge")
        if global_cli and probe_command([global_cli]):
            return [global_cli]
    return None


def safe_extract(zip_file: zipfile.ZipFile, target: Path) -> None:
    target_root = target.resolve()
    for member in zip_file.infolist():
        member_path = PurePosixPath(member.filename)
        mode = (member.external_attr >> 16) & 0o170000
        if member_path.is_absolute() or ".." in member_path.parts or mode == stat.S_IFLNK:
            raise BootstrapError(40, "blocked_access", "引擎 ZIP 包含不安全的文件路径")
        destination = (target / Path(*member_path.parts)).resolve()
        if destination != target_root and target_root not in destination.parents:
            raise BootstrapError(40, "blocked_access", "引擎 ZIP 试图写出目标目录")
    zip_file.extractall(target)


def remove_readonly(func, path, _exc_info) -> None:
    os.chmod(path, stat.S_IWRITE)
    func(path)


def download_source(engine_dir: Path) -> None:
    engine_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="knowledge-engine-") as temp_name:
        temp_dir = Path(temp_name)
        last_error: Exception | None = None
        for branch in ("main", "master"):
            zip_path = temp_dir / f"engine-{branch}.zip"
            url = ENGINE_ZIP_BASE.format(branch)
            try:
                with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT) as response:
                    with zip_path.open("wb") as output:
                        shutil.copyfileobj(response, output)
                extract_dir = temp_dir / f"source-{branch}"
                extract_dir.mkdir()
                with zipfile.ZipFile(zip_path) as archive:
                    safe_extract(archive, extract_dir)
                source_root = next(
                    (
                        path
                        for path in extract_dir.iterdir()
                        if path.is_dir() and (path / "mcp" / "pyproject.toml").is_file()
                    ),
                    None,
                )
                if source_root is None:
                    raise BootstrapError(40, "blocked_access", "ZIP 中没有找到引擎的 mcp/pyproject.toml")
                shutil.copytree(source_root, engine_dir)
                return
            except BootstrapError:
                raise
            except (OSError, ValueError, http.client.HTTPException, urllib.error.URLError, zipfile.BadZipFile) as exc:
                last_error = exc
        raise BootstrapError(20, "no_network", f"无法从 GitHub 下载引擎: {last_error}")


def ensure_source(engine_dir: Path) -> None:
    pyproject = engine_dir / "mcp" / "pyproject.toml"
    if pyproject.is_file():
        return
    try:
        if engine_dir.exists() and any(engine_dir.iterdir()):
            raise BootstrapError(40, "blocked_access", f"引擎目录已存在但不是有效仓库: {engine_dir}")
        engine_dir.parent.mkdir(parents=True, exist_ok=True)
    except BootstrapError:
        raise
    except OSError as exc:
        raise BootstrapError(40, "blocked_access", f"无法检查或创建引擎目录 {engine_dir}: {exc}") from exc
    if engine_dir.exists():
        engine_dir.rmdir()

    git = shutil.which("git")
    if git:
        try:
            subprocess.run(
                [git, "clone", "--depth", "1", ENGINE_REPOSITORY, str(engine_dir)],
                check=True,
                timeout=DOWNLOAD_TIMEOUT,
                env=command_env(),
            )
            return
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            if engine_dir.exists():
                shutil.rmtree(engine_dir, onerror=remove_readonly)
            print(f"git clone 失败，改用 GitHub ZIP: {exc}", file=sys.stderr)
    download_source(engine_dir)


def pip_install(engine_python: Path, engine_dir: Path) -> None:
    install_command = [
        str(engine_python),
        "-m",
        "pip",
        "install",
        "-e",
        str(engine_dir / "mcp"),
    ]
    try:
        result = subprocess.run(install_command, env=command_env(), timeout=INSTALL_TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BootstrapError(40, "blocked_access", f"无法运行 venv 的 pip: {exc}") from exc
    if result.returncode == 0:
        return

    print("默认 PyPI 源失败，重试清华镜像。", file=sys.stderr)
    try:
        result = subprocess.run(
            [*install_command, "-i", MIRROR],
            env=command_env(),
            timeout=INSTALL_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BootstrapError(40, "blocked_access", f"无法运行镜像安装命令: {exc}") from exc
    if result.returncode != 0:
        raise BootstrapError(20, "no_network", "Python 依赖安装失败，请检查网络、代理或 pip 源")


def install_engine(engine_dir: Path, allow_global: bool) -> list[str]:
    if sys.version_info < (3, 11):
        raise BootstrapError(10, "needs_python", "需要 Python 3.11 或更高版本")

    engine_dir = engine_dir.expanduser().resolve()
    cli = find_working_cli(engine_dir, allow_global)
    if cli:
        return cli

    try:
        ensure_source(engine_dir)
    except BootstrapError:
        raise
    except OSError as exc:
        raise BootstrapError(40, "blocked_access", f"无法准备引擎目录 {engine_dir}: {exc}") from exc

    engine_python = venv_python(engine_dir)
    if not engine_python.is_file():
        try:
            subprocess.run(
                [sys.executable, "-m", "venv", str(engine_dir / ".venv")],
                check=True,
                timeout=DOWNLOAD_TIMEOUT,
                env=command_env(),
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise BootstrapError(40, "blocked_access", f"无法创建虚拟环境 {engine_dir / '.venv'}: {exc}") from exc

    if not probe_command(cli_module_command(engine_dir), engine_dir):
        pip_install(engine_python, engine_dir)

    cli = find_working_cli(engine_dir, allow_global=False)
    if not cli:
        raise BootstrapError(40, "blocked_access", "依赖已安装，但 knowledge_mcp.cli 仍不可执行")
    return cli


def require_library(value: str | None, cli_args: list[str]) -> Path:
    raw = value or os.environ.get("KNOWLEDGE_ROOT")
    if not raw:
        raise BootstrapError(30, "need_library", "请先确认知识库的绝对路径，并用 --library 传入")
    root = Path(raw).expanduser()
    if not root.is_absolute():
        raise BootstrapError(30, "need_library", f"知识库路径必须是绝对路径: {raw}")
    root = root.resolve()
    initializing = bool(cli_args) and cli_args[0] == "init"
    if not root.exists():
        if initializing:
            return root
        raise BootstrapError(30, "need_library", f"知识库目录不存在；新库请先运行 init: {root}")
    if not root.is_dir():
        raise BootstrapError(30, "need_library", f"知识库路径不是目录: {root}")
    if not initializing and not ((root / "原始资料").is_dir() or (root / "资料").is_dir()):
        raise BootstrapError(30, "need_library", f"目录不像已初始化的知识库，请确认路径或先运行 init: {root}")
    return root


def parse_args(argv: list[str]) -> argparse.Namespace:
    usage = "用法: bootstrap.py ensure | bootstrap.py run --library <绝对路径> -- <knowledge 参数>"
    if not argv:
        raise SystemExit(usage)
    if argv[0] in {"-h", "--help"}:
        print(usage)
        raise SystemExit(0)

    action = argv[0]
    if action == "ensure":
        parser = argparse.ArgumentParser(description="准备并验证本地 knowledge CLI")
        parser.add_argument("--engine-dir", type=Path, default=None)
        args = parser.parse_args(argv[1:])
        args.action = action
        args.cli_args = []
        return args

    if action != "run":
        raise SystemExit(f"未知操作: {action}")

    tokens = argv[1:]
    if "--" in tokens:
        separator = tokens.index("--")
        option_tokens, cli_args = tokens[:separator], tokens[separator + 1 :]
    else:
        option_tokens = []
        cli_args = list(tokens)
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token == "--library" or token == "--engine-dir":
                if index + 1 >= len(tokens):
                    raise SystemExit(f"{token} 需要一个值")
                option_tokens.extend(tokens[index : index + 2])
                index += 2
                continue
            if token.startswith("-"):
                raise SystemExit("run 的 knowledge 参数请放在 -- 之后")
            cli_args = tokens[index:]
            break
        else:
            cli_args = []

    parser = argparse.ArgumentParser(description="在明确的知识库路径下运行 knowledge CLI")
    parser.add_argument("--library", type=str, default=None)
    parser.add_argument("--engine-dir", type=Path, default=None)
    args = parser.parse_args(option_tokens)
    args.action = action
    args.cli_args = cli_args
    if not args.cli_args:
        raise SystemExit("run 后面需要 knowledge 子命令")
    return args


def main(argv: list[str] | None = None) -> int:
    configure_output()
    try:
        args = parse_args(list(sys.argv[1:] if argv is None else argv))
        root = require_library(args.library, args.cli_args) if args.action == "run" else None
        engine_dir = (args.engine_dir or default_engine_dir()).expanduser().resolve()
        cli = install_engine(engine_dir, allow_global=args.engine_dir is None)
        if args.action == "ensure":
            print("status=ready")
            print(f"engine_dir={engine_dir}")
            print(f"cli={cli!r}")
            return 0

        env = command_env(root)
        print(f"status=ready")
        print(f"knowledge_root={root}")
        return subprocess.run([*cli, *args.cli_args], env=env, check=False).returncode
    except BootstrapError as exc:
        print(f"status={exc.status}", file=sys.stderr)
        print(exc.message, file=sys.stderr)
        return exc.code
    except SystemExit as exc:
        if exc.code == 0:
            return 0
        print("status=blocked_access", file=sys.stderr)
        print("bootstrap 参数错误；按用法修正命令后重试。", file=sys.stderr)
        return 40
    except (OSError, PermissionError) as exc:
        print("status=blocked_access", file=sys.stderr)
        print(f"操作失败: {exc}", file=sys.stderr)
        return 40


if __name__ == "__main__":
    raise SystemExit(main())
