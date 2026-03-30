"""Test yaml_utils module for DRY YAML config loading."""

from pathlib import Path
import pytest


def test_yaml_utils_module_exists():
    """yaml_utils.py 应该存在"""
    yaml_utils_path = Path("tools/lib/yaml_utils.py")
    assert yaml_utils_path.exists(), "tools/lib/yaml_utils.py 不存在"


def test_load_yaml_config_returns_dict(tmp_path):
    """有效的 YAML 文件应返回 dict"""
    from tools.lib.yaml_utils import load_yaml_config

    config_file = tmp_path / "test.yaml"
    config_file.write_text("key: value\nnested:\n  inner: 42\n", encoding="utf-8")
    result = load_yaml_config(config_file)
    assert result == {"key": "value", "nested": {"inner": 42}}


def test_load_yaml_config_missing_file(tmp_path):
    """不存在的文件应返回空 dict，不抛异常"""
    from tools.lib.yaml_utils import load_yaml_config

    result = load_yaml_config(tmp_path / "nonexistent.yaml")
    assert result == {}


def test_load_yaml_config_invalid_yaml(tmp_path):
    """无效 YAML 应返回空 dict，不抛异常"""
    from tools.lib.yaml_utils import load_yaml_config

    config_file = tmp_path / "bad.yaml"
    config_file.write_text("{{{{invalid yaml", encoding="utf-8")
    result = load_yaml_config(config_file)
    assert result == {}


def test_deep_merge_basic():
    """深度合并：override 覆盖 base"""
    from tools.lib.yaml_utils import deep_merge

    base = {"a": 1, "b": {"c": 2, "d": 3}}
    override = {"b": {"c": 99, "e": 5}}
    result = deep_merge(base, override)
    assert result == {"a": 1, "b": {"c": 99, "d": 3, "e": 5}}


def test_deep_merge_does_not_mutate_base():
    """合并不应修改原始 dict"""
    from tools.lib.yaml_utils import deep_merge

    base = {"a": {"b": 1}}
    override = {"a": {"c": 2}}
    result = deep_merge(base, override)
    assert base == {"a": {"b": 1}}  # 原始未被修改
    assert result == {"a": {"b": 1, "c": 2}}


def test_deep_merge_empty_override():
    """空 override 应返回 base 的副本"""
    from tools.lib.yaml_utils import deep_merge

    base = {"a": 1}
    result = deep_merge(base, {})
    assert result == {"a": 1}


def test_paths_imports_from_yaml_utils():
    """paths.py 应从 yaml_utils 导入函数"""
    source = Path("tools/lib/paths.py").read_text(encoding="utf-8")
    assert "from .yaml_utils import" in source, "paths.py 未从 yaml_utils 导入"


def test_config_imports_from_yaml_utils():
    """config.py 应从 yaml_utils 导入函数"""
    source = Path("tools/lib/config.py").read_text(encoding="utf-8")
    assert "from .yaml_utils import" in source, "config.py 未从 yaml_utils 导入"
