#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TempDataDirResult:
    temp_root: str
    data_dir: str
    source_data_dir: str | None
    seeded: bool
    shell_command: str = ""
    mode: str = "generic"
    safe_to_delete_after: bool = True
    shell_snippet: str = ""
    cleanup_command: str = ""
    next_steps: list[str] = field(default_factory=list)
    summary: dict[str, int] = field(
        default_factory=lambda: {
            "created": 0,
            "seeded": 0,
            "cleaned": 0,
        }
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "temp_root": self.temp_root,
            "data_dir": self.data_dir,
            "source_data_dir": self.source_data_dir,
            "seeded": self.seeded,
            "shell_command": self.shell_command,
            "mode": self.mode,
            "safe_to_delete_after": self.safe_to_delete_after,
            "shell_snippet": self.shell_snippet,
            "cleanup_command": self.cleanup_command,
            "next_steps": list(self.next_steps),
            "summary": dict(self.summary),
        }


class TempDataDirSession:
    def __init__(
        self,
        *,
        base_tmp_dir: Path | None = None,
        source_data_dir: Path | None = None,
        seed: bool = False,
        name: str | None = None,
    ) -> None:
        self.base_tmp_dir = base_tmp_dir
        self.source_data_dir = source_data_dir
        self.seed = seed
        self.name = name
        self.temp_root: Path | None = None
        self.data_dir: Path | None = None

    def prepare(self, *, cleanup_now: bool = False) -> TempDataDirResult:
        prefix = "life_index_manual_"
        if self.name:
            safe_name = self.name.replace(" ", "-")
            prefix = f"life_index_manual_{safe_name}_"

        if self.base_tmp_dir is None:
            temp_root = Path(tempfile.mkdtemp(prefix=prefix))
        else:
            self.base_tmp_dir.mkdir(parents=True, exist_ok=True)
            temp_root = Path(tempfile.mkdtemp(prefix=prefix, dir=str(self.base_tmp_dir)))

        data_dir = temp_root / "Life-Index"
        data_dir.mkdir(parents=True, exist_ok=True)

        seeded = False
        if self.seed and self.source_data_dir is not None:
            self._copy_tree(self.source_data_dir, data_dir)
            seeded = True

        self.temp_root = temp_root
        self.data_dir = data_dir

        command_parts = [f"set LIFE_INDEX_DATA_DIR={data_dir}"]
        command_parts.append("life-index health")
        command_parts.append("life-index index")
        shell_command = " && ".join(command_parts)
        shell_snippet = shell_command
        cleanup_command = f'Remove-Item -Recurse -Force "{temp_root}"'

        summary = {
            "created": 1,
            "seeded": 1 if seeded else 0,
            "cleaned": 0,
        }

        next_steps = [
            f"设置 LIFE_INDEX_DATA_DIR={data_dir}",
            "运行 life-index health 检查当前环境",
            "运行 life-index index 初始化隔离索引",
            "在该隔离目录上执行手工调试或验收",
        ]

        result = TempDataDirResult(
            temp_root=str(temp_root),
            data_dir=str(data_dir),
            source_data_dir=str(self.source_data_dir) if self.source_data_dir else None,
            seeded=seeded,
            shell_command=shell_command,
            mode="generic",
            safe_to_delete_after=True,
            shell_snippet=shell_snippet,
            cleanup_command=cleanup_command,
            next_steps=next_steps,
            summary=summary,
        )

        if cleanup_now:
            self.cleanup()
            result.summary["cleaned"] = 1

        return result

    def cleanup(self) -> None:
        if self.temp_root and self.temp_root.exists():
            shutil.rmtree(self.temp_root, ignore_errors=True)

    def _copy_tree(self, source: Path, destination: Path) -> None:
        for item in source.iterdir():
            target = destination / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)


def print_report(result: TempDataDirResult, *, use_json: bool = False) -> None:
    if use_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return

    print("=" * 60)
    print("Life Index 手工调试隔离目录")
    print("=" * 60)
    print(f"临时根目录: {result.temp_root}")
    print(f"数据目录: {result.data_dir}")
    if result.source_data_dir:
        print(f"种子来源: {result.source_data_dir}")
    print()
    print("使用方式:")
    print(f"  set LIFE_INDEX_DATA_DIR={result.data_dir}")
    print("  life-index health")
    print("  life-index index")
    print()
    print("完整命令:")
    print(f"  {result.shell_command}")
    print()
    print("后续建议:")
    print("  - 在该隔离目录内执行写入 / 搜索 / 编辑等调试")
    print("  - 若曾误写真实用户目录，请执行 `life-index index --rebuild`")
    print()
    print("完成后请删除该临时目录，避免留下调试污染。")


def main() -> None:
    from ...lib.paths import get_user_data_dir

    parser = argparse.ArgumentParser(description="Life Index 手工调试隔离目录工具")
    parser.add_argument("--seed", action="store_true", help="复制当前用户数据到临时目录")
    parser.add_argument("--name", help="为本次沙盒目录添加可读标签")
    parser.add_argument(
        "--cleanup-now",
        action="store_true",
        help="创建后立即删除，用于验证清理流程",
    )
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    session = TempDataDirSession(
        source_data_dir=get_user_data_dir(),
        seed=args.seed,
        name=args.name,
    )
    result = session.prepare(cleanup_now=args.cleanup_now)
    print_report(result, use_json=args.json)


if __name__ == "__main__":
    main()
