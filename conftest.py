"""
pytest conftest.py - 项目级测试配置

将项目根加入 sys.path，使测试文件可以使用完整包路径导入：
  from tools.lib.xxx import ...        # 共享库（完整路径）
  from tools.write_journal.xxx import  # 工具模块（完整路径）

所有测试文件无需再手动操作 sys.path。
"""

import os
import sys
from pathlib import Path
from typing import Generator

import pytest

# 项目根目录（conftest.py 所在目录）
PROJECT_ROOT = Path(__file__).parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# 隔离数据目录 Fixture（防止测试污染生产数据）
# ============================================================


@pytest.fixture(scope="function")
def isolated_data_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """
    为每个测试创建隔离的数据目录，防止测试污染生产数据。

    使用方式：
        def test_something(isolated_data_dir):
            # isolated_data_dir 是临时目录
            # 设置环境变量后，config.USER_DATA_DIR 会指向此目录
            ...

    原理：
        1. 创建临时目录
        2. 设置 LIFE_INDEX_DATA_DIR 环境变量
        3. 重新加载 config 模块以应用新的 USER_DATA_DIR
        4. 测试结束后恢复环境变量和模块状态
    """
    # 保存原始环境变量
    original_env = os.environ.get("LIFE_INDEX_DATA_DIR")

    # 设置新的数据目录
    test_data_dir = tmp_path / "Life-Index"
    test_data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["LIFE_INDEX_DATA_DIR"] = str(test_data_dir)

    # 重新加载 config 模块以应用新的 USER_DATA_DIR
    # 这会影响所有依赖 config 的模块
    import importlib
    import tools.lib.config as config_module

    importlib.reload(config_module)

    # 同样需要重新加载依赖 config 的模块
    import tools.lib.vector_index_simple as vec_module

    importlib.reload(vec_module)

    try:
        yield test_data_dir
    finally:
        # 恢复环境变量
        if original_env is not None:
            os.environ["LIFE_INDEX_DATA_DIR"] = original_env
        elif "LIFE_INDEX_DATA_DIR" in os.environ:
            del os.environ["LIFE_INDEX_DATA_DIR"]

        # 重新加载模块以恢复原始状态
        importlib.reload(config_module)
        importlib.reload(vec_module)


@pytest.fixture(scope="function")
def isolated_vector_index(isolated_data_dir: Path) -> Generator[None, None, None]:
    """
    为测试提供隔离的向量索引。

    使用方式：
        def test_vector_search(isolated_vector_index):
            from tools.lib.vector_index_simple import get_index
            index = get_index()
            # index 现在指向临时目录中的索引
            ...

    注意：
        此 fixture 依赖 isolated_data_dir，确保向量索引存储在临时目录中。
    """
    # isolated_data_dir 已经设置了环境和重新加载了模块
    # 只需要重置向量索引的全局实例
    import tools.lib.vector_index_simple as vec_module

    vec_module._index_instance = None

    yield

    # 清理：重置全局实例
    vec_module._index_instance = None
