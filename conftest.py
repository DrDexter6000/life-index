"""
pytest conftest.py - 项目级测试配置

将项目根加入 sys.path，使测试文件可以使用完整包路径导入：
  from tools.lib.xxx import ...        # 共享库（完整路径）
  from tools.write_journal.xxx import  # 工具模块（完整路径）

所有测试文件无需再手动操作 sys.path。

测试数据隔离机制 (Round 15)：
    1. 模块级代码设置 LIFE_INDEX_DATA_DIR 环境变量到临时目录
    2. 所有工具模块通过 get_user_data_dir() 读取此环境变量
    3. 不需要 monkeypatch — 环境变量在 import 之前已设置
    4. pytest guard 确保 unset 时立即崩溃而非静默写入真实目录
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Generator

import pytest

# 项目根目录（conftest.py 所在目录）
PROJECT_ROOT = Path(__file__).parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# 全局测试隔离：在 import 任何工具模块之前设置环境变量
# ============================================================
# pytest 加载 conftest.py 在收集测试模块之前执行，
# 因此这里的代码在所有 test_*.py 的顶层 import 之前运行。
# tools/lib/paths.py 的 get_user_data_dir() 会读取此环境变量。

# 保存原始值（通常为 None）
_ORIG_LIFE_INDEX_DATA_DIR = os.environ.get("LIFE_INDEX_DATA_DIR")

# 创建会话级临时数据目录
_SESSION_TMP_DIR = Path(tempfile.mkdtemp(prefix="life-index-test-"))
os.environ["LIFE_INDEX_DATA_DIR"] = str(_SESSION_TMP_DIR)

# 创建基础目录结构
(_SESSION_TMP_DIR / "Journals").mkdir(parents=True, exist_ok=True)
(_SESSION_TMP_DIR / ".index").mkdir(parents=True, exist_ok=True)
(_SESSION_TMP_DIR / ".cache").mkdir(parents=True, exist_ok=True)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """测试会话结束后清理临时目录。"""
    # 恢复环境变量
    if _ORIG_LIFE_INDEX_DATA_DIR is not None:
        os.environ["LIFE_INDEX_DATA_DIR"] = _ORIG_LIFE_INDEX_DATA_DIR
    elif "LIFE_INDEX_DATA_DIR" in os.environ:
        del os.environ["LIFE_INDEX_DATA_DIR"]

    # 清理临时目录
    if _SESSION_TMP_DIR.exists():
        try:
            shutil.rmtree(_SESSION_TMP_DIR, ignore_errors=True)
        except Exception:
            pass


# ============================================================
# 隔离数据目录 Fixture（每个测试函数独立临时目录）
# ============================================================


@pytest.fixture(scope="function")
def isolated_data_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """
    为每个测试创建隔离的数据目录，防止测试间数据干扰。

    使用方式：
        def test_something(isolated_data_dir):
            # isolated_data_dir 是临时目录
            # get_user_data_dir() 返回此目录
            ...

    原理 (Round 15 简化版)：
        1. 创建临时目录
        2. 设置 LIFE_INDEX_DATA_DIR 环境变量指向此目录
        3. get_user_data_dir() 自动读取新值（无缓存，状态无关）
        4. 测试结束后恢复环境变量到会话级临时目录

    不需要 monkeypatch 或 importlib.reload —
    环境变量是唯一的路径解析机制。
    """
    test_data_dir = tmp_path / "Life-Index"
    journals_dir = test_data_dir / "Journals"
    journals_dir.mkdir(parents=True, exist_ok=True)
    index_dir = test_data_dir / ".index"
    index_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = test_data_dir / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # 保存当前 env var（会话级临时目录）
    prev_env = os.environ.get("LIFE_INDEX_DATA_DIR")

    # 设置到 per-test 临时目录
    os.environ["LIFE_INDEX_DATA_DIR"] = str(test_data_dir)

    # 重置向量索引全局实例（如果已加载）
    try:
        import tools.lib.vector_index_simple as vec_module
        vec_module._index_instance = None
    except ImportError:
        pass

    try:
        yield test_data_dir
    finally:
        # 恢复到会话级临时目录
        if prev_env is not None:
            os.environ["LIFE_INDEX_DATA_DIR"] = prev_env
        else:
            os.environ["LIFE_INDEX_DATA_DIR"] = str(_SESSION_TMP_DIR)

        # 重置向量索引全局实例
        try:
            import tools.lib.vector_index_simple as vec_module
            vec_module._index_instance = None
        except ImportError:
            pass


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
    import tools.lib.vector_index_simple as vec_module

    vec_module._index_instance = None

    yield

    vec_module._index_instance = None
