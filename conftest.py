"""
pytest conftest.py - 项目级测试配置

将项目根加入 sys.path，使测试文件可以使用完整包路径导入：
  from tools.lib.xxx import ...        # 共享库（完整路径）
  from tools.write_journal.xxx import  # 工具模块（完整路径）

所有测试文件无需再手动操作 sys.path。
"""

import sys
from pathlib import Path

# 项目根目录（conftest.py 所在目录）
PROJECT_ROOT = Path(__file__).parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
