#!/usr/bin/env python3
"""
Life Index - Logging Module
结构化日志模块

设计原则：
- Console 输出到 stderr（Agent 忽略）
- JSON 结果输出到 stdout（Agent 解析）
- 文件日志使用 JSON 格式（调试用）
- 跨平台兼容

Usage:
    from tools.lib.logger import get_logger

    logger = get_logger("write_journal")
    logger.info("Writing journal...")
    # 输出到 stderr，不污染 stdout
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """
    JSON 结构化日志格式化器

    Agent 可直接解析 JSON 格式的日志，便于调试和监控。
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # 添加额外字段
        if hasattr(record, "extra_data") and record.extra_data:
            log_data["data"] = record.extra_data

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


class HumanFormatter(logging.Formatter):
    """
    人类可读格式（用于 console 输出）
    """

    def format(self, record: logging.LogRecord) -> str:
        # 简洁格式：级别: 消息
        if record.levelno >= logging.WARNING:
            return f"[{record.levelname}] {record.name}: {record.getMessage()}"
        return f"[{record.levelname}] {record.getMessage()}"


def setup_logger(
    name: str = "life-index",
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    json_format: bool = False,
    verbose: bool = False,
) -> logging.Logger:
    """
    配置并返回日志器

    Args:
        name: 日志器名称
        level: 日志级别（默认 INFO）
        log_file: 日志文件路径（可选）
        json_format: 是否使用 JSON 格式（默认 False，人类可读）
        verbose: 是否输出详细信息（DEBUG 级别）

    Returns:
        配置好的 Logger 实例

    设计要点：
        - Console handler 输出到 stderr（Agent 不解析 stderr）
        - File handler 使用 JSON 格式（便于调试分析）
        - JSON 结果始终通过 stdout 输出（由工具函数控制）
    """
    logger = logging.getLogger(name)

    # 设置日志级别
    if verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(level)

    # 清除现有 handlers（避免重复）
    logger.handlers.clear()

    # Console handler（输出到 stderr，不污染 stdout）
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.DEBUG if verbose else level)

    if json_format:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(HumanFormatter())

    logger.addHandler(console_handler)

    # File handler（可选，用于调试）
    if log_file:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(JSONFormatter())  # 文件始终用 JSON
            logger.addHandler(file_handler)
        except (OSError, IOError) as e:
            logger.warning(f"无法创建日志文件: {e}")

    return logger


def get_logger(name: str = "life-index") -> logging.Logger:
    """
    获取日志器实例

    如果日志器未配置，将使用默认配置初始化。

    Args:
        name: 日志器名称（默认 "life-index"）

    Returns:
        Logger 实例
    """
    logger = logging.getLogger(name)

    # 如果未配置，使用默认配置
    if not logger.handlers:
        return setup_logger(name)

    return logger


def get_default_log_file() -> Path:
    """
    获取默认日志文件路径

    Returns:
        日志文件路径（跨平台）
    """
    # 使用用户数据目录下的 .logs 目录
    from pathlib import Path

    if sys.platform == "win32":
        # Windows: %USERPROFILE%\\Documents\\Life-Index\\.logs
        base_dir = Path.home() / "Documents" / "Life-Index"
    else:
        # macOS/Linux: ~/Documents/Life-Index/.logs
        base_dir = Path.home() / "Documents" / "Life-Index"

    return base_dir / ".logs" / "life-index.log"


class LoggerAdapter(logging.LoggerAdapter):
    """
    日志适配器，支持额外数据

    Usage:
        logger = get_logger("my_module")
        adapter = LoggerAdapter(logger, {"module": "write_journal"})
        adapter.info("Processing...", extra_data={"file": "test.md"})
    """

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        # 合并额外数据
        extra_data = kwargs.pop("extra_data", {})
        if self.extra:
            extra_data.update(self.extra)

        if extra_data:
            kwargs.setdefault("extra", {})["extra_data"] = extra_data

        return msg, kwargs


# 全局默认日志器
_default_logger: Optional[logging.Logger] = None


def init_logging(
    verbose: bool = False, log_file: Optional[Path] = None
) -> logging.Logger:
    """
    初始化全局日志配置

    应在程序入口调用一次。

    Args:
        verbose: 是否启用详细日志
        log_file: 日志文件路径（可选）

    Returns:
        配置好的默认日志器
    """
    global _default_logger

    _default_logger = setup_logger(
        name="life-index",
        level=logging.DEBUG if verbose else logging.INFO,
        log_file=log_file,
        verbose=verbose,
    )

    return _default_logger


if __name__ == "__main__":
    # 测试代码
    logger = get_logger("test")

    print("Testing logger...")

    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

    # 测试带额外数据的日志
    adapter = LoggerAdapter(logger, {"component": "test_module"})
    adapter.info("Processing file", extra_data={"file": "test.md", "lines": 100})

    print("\nJSON format test:")
    json_logger = setup_logger("json_test", json_format=True)
    json_logger.info("This is a JSON formatted message")
