# Vector Index Pollution Fix

> **日期**: 2026-03-18
> **优先级**: High
> **状态**: 已完成

---

## 1. 问题描述

### 发现过程

Investigation #3 (Retrieval Quality) 运行时验证时发现搜索结果数量异常：

```
实际日志文件: 22篇
搜索返回结果: 50篇
向量索引数量: 187个
```

### 根本原因

单元测试污染生产向量索引：

1. 测试在 `pytest-of-xxx/` 临时目录创建日志文件
2. 测试过程中这些文件路径被写入全局向量索引
3. pytest 默认保留最近3个测试会话的临时目录
4. 索引中存储了这些临时文件的绝对路径
5. 临时文件删除后，索引中仍保留陈旧向量

### 影响

- 搜索返回不存在的文件
- 搜索结果数量不准确
- 索引大小膨胀

---

## 2. 修复方案

### 方案A: 测试隔离

**实现**: 修改 `conftest.py` 添加隔离fixture

```python
@pytest.fixture(scope="function")
def isolated_data_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """为每个测试创建隔离的数据目录"""
    # 设置 LIFE_INDEX_DATA_DIR 环境变量
    # 重新加载 config 模块
    ...

@pytest.fixture(scope="function")
def isolated_vector_index(isolated_data_dir: Path):
    """为测试提供隔离的向量索引"""
    ...
```

**配合修改**: `config.py` 支持环境变量 `LIFE_INDEX_DATA_DIR`

```python
_user_data_env = os.environ.get("LIFE_INDEX_DATA_DIR")
if _user_data_env:
    USER_DATA_DIR = Path(_user_data_env)
else:
    USER_DATA_DIR = Path.home() / "Documents" / "Life-Index"
```

### 方案B: 自动清理陈旧向量

**实现**: 在 `vector_index_simple.py` 的 `SimpleVectorIndex._load()` 中添加清理逻辑

```python
def _load(self):
    """从磁盘加载索引"""
    if VEC_INDEX_PATH.exists():
        try:
            with open(VEC_INDEX_PATH, "rb") as f:
                self.vectors = pickle.load(f)
            # 加载后自动清理陈旧向量
            self._cleanup_stale_vectors()
        except Exception as e:
            ...

def _cleanup_stale_vectors(self) -> int:
    """清理指向不存在文件的陈旧向量"""
    stale_paths = []
    for path in self.vectors.keys():
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = USER_DATA_DIR / path
        if not file_path.exists():
            stale_paths.append(path)
    
    for path in stale_paths:
        del self.vectors[path]
    
    if stale_paths:
        self._save()
        print(f"[INFO] Cleaned {len(stale_paths)} stale vectors from index")
    
    return len(stale_paths)
```

---

## 3. 验证结果

### 方案B测试

```
写入测试索引: 3个向量 (1个存在, 2个不存在)
加载后向量数: 1
[INFO] Cleaned 2 stale vectors from index
SUCCESS: 方案B工作正常
```

### 单元测试

```
755 passed, 4 skipped
```

---

## 4. 修改文件

| 文件 | 修改内容 |
|:---|:---|
| `tools/lib/config.py` | 添加 `LIFE_INDEX_DATA_DIR` 环境变量支持 |
| `conftest.py` | 添加 `isolated_data_dir` 和 `isolated_vector_index` fixture |
| `tools/lib/vector_index_simple.py` | 添加 `_cleanup_stale_vectors()` 方法 |

---

## 5. 后续建议

### 新测试

新测试应使用 `isolated_data_dir` fixture 以完全隔离：

```python
def test_something(isolated_data_dir):
    # isolated_data_dir 是临时目录
    # config.USER_DATA_DIR 指向此目录
    ...
```

### 现有测试

现有测试已经使用 mock 隔离大部分索引操作。方案B 提供了双重保护：
- 测试期间：mock 防止写入
- 测试后：自动清理陈旧向量

### 维护

定期运行 `python -m tools.build_index --rebuild` 可完全重建索引。

---

## 6. Evidence Classification

| 项目 | Tier |
|:---|:---:|
| 问题存在 | A (运行时验证) |
| 根因分析 | A (代码分析) |
| 修复实现 | A (代码变更) |
| 修复验证 | A (测试通过) |