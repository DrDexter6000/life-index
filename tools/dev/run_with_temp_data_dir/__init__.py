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
    serve_command: str = ""
    for_web: bool = False
    web_url: str = "http://127.0.0.1:8765/"
    readonly_simulation: bool = False
    mode: str = "generic"
    browser_url: str = "http://127.0.0.1:8765/"
    safe_to_delete_after: bool = True
    shell_snippet: str = ""
    cleanup_command: str = ""
    next_steps: list[str] = field(default_factory=list)
    acceptance_checklist: list[str] = field(default_factory=list)
    post_acceptance_actions: list[str] = field(default_factory=list)
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
            "serve_command": self.serve_command,
            "for_web": self.for_web,
            "web_url": self.web_url,
            "readonly_simulation": self.readonly_simulation,
            "mode": self.mode,
            "browser_url": self.browser_url,
            "safe_to_delete_after": self.safe_to_delete_after,
            "shell_snippet": self.shell_snippet,
            "cleanup_command": self.cleanup_command,
            "next_steps": list(self.next_steps),
            "acceptance_checklist": list(self.acceptance_checklist),
            "post_acceptance_actions": list(self.post_acceptance_actions),
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
        for_web: bool = False,
    ) -> None:
        self.base_tmp_dir = base_tmp_dir
        self.source_data_dir = source_data_dir
        self.seed = seed
        self.name = name
        self.for_web = for_web
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

        readonly_simulation = bool(seeded and self.for_web)
        command_parts = [f"set LIFE_INDEX_DATA_DIR={data_dir}"]
        if readonly_simulation:
            command_parts.append("set LIFE_INDEX_READONLY_SIMULATION=1")
        command_parts.append("life-index serve --host 127.0.0.1 --port 8765")
        serve_command = " && ".join(command_parts)
        shell_snippet = serve_command
        cleanup_command = f'Remove-Item -Recurse -Force "{temp_root}"'

        summary = {
            "created": 1,
            "seeded": 1 if seeded else 0,
            "cleaned": 0,
        }

        acceptance_checklist = []
        post_acceptance_actions = []
        next_steps = [
            f"设置 LIFE_INDEX_DATA_DIR={data_dir}",
            "启动 life-index serve",
            "在浏览器打开 http://127.0.0.1:8765/",
        ]
        if self.for_web:
            acceptance_checklist = [
                "打开 Dashboard 首页",
                "检查 topic 图和统计卡片",
                "检查搜索页 drill-down",
                "检查 journal 页面跳转",
                "检查 attachment 渲染",
            ]
            post_acceptance_actions = [
                "若只是临时验收，直接删除临时目录",
                "若你在沙盒中进行了需要保留的结构化修改，请先人工确认，再决定是否迁回真实目录",
                "若曾误写真实用户目录，请执行 `life-index index --rebuild`",
            ]
            next_steps.extend(
                [
                    "按清单完成 Dashboard / Search / Journal / Attachment 验收",
                    "验收完成后删除临时目录，或按需保留结果供人工复核",
                ]
            )

        result = TempDataDirResult(
            temp_root=str(temp_root),
            data_dir=str(data_dir),
            source_data_dir=str(self.source_data_dir) if self.source_data_dir else None,
            seeded=seeded,
            serve_command=serve_command,
            for_web=self.for_web,
            readonly_simulation=readonly_simulation,
            mode="web_acceptance" if self.for_web else "generic",
            browser_url="http://127.0.0.1:8765/",
            safe_to_delete_after=True,
            shell_snippet=shell_snippet,
            cleanup_command=cleanup_command,
            next_steps=next_steps,
            acceptance_checklist=acceptance_checklist,
            post_acceptance_actions=post_acceptance_actions,
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
    if result.readonly_simulation:
        print("模式: 只读仿真验收（复制数据）")
    print()
    print("使用方式:")
    print(f"  set LIFE_INDEX_DATA_DIR={result.data_dir}")
    print("  life-index serve")
    print()
    print("完整启动命令:")
    print(f"  {result.serve_command}")
    print(f"  打开: {result.web_url}")
    if result.for_web:
        print()
        print("Web GUI 验收清单:")
        for index, item in enumerate(result.acceptance_checklist, start=1):
            print(f"  {index}. {item}")
    if result.readonly_simulation:
        print()
        print("说明:")
        print("  当前为只读仿真验收，使用的是复制后的数据副本。")
        print("  本次调试不会回写真实用户目录。")
    print()
    if result.for_web:
        print("验收后建议:")
        for item in result.post_acceptance_actions:
            print(f"  - {item}")
        print()
    print("完成后请删除该临时目录，避免留下调试污染。")


def main() -> None:
    from ...lib.config import USER_DATA_DIR

    parser = argparse.ArgumentParser(description="Life Index 手工调试隔离目录工具")
    parser.add_argument("--seed", action="store_true", help="复制当前用户数据到临时目录")
    parser.add_argument("--name", help="为本次沙盒目录添加可读标签")
    parser.add_argument(
        "--cleanup-now",
        action="store_true",
        help="创建后立即删除，用于验证清理流程",
    )
    parser.add_argument(
        "--for-web",
        action="store_true",
        help="输出 Web GUI 验收模式提示与清单",
    )
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    session = TempDataDirSession(
        source_data_dir=USER_DATA_DIR,
        seed=args.seed,
        name=args.name,
        for_web=args.for_web,
    )
    result = session.prepare(cleanup_now=args.cleanup_now)
    print_report(result, use_json=args.json)


if __name__ == "__main__":
    main()
