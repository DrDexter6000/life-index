"""Audit index state vs actual journal data."""
import sqlite3
import os
import json
import pickle
from pathlib import Path
from datetime import datetime

data_dir = Path(os.path.expanduser("~")) / "Documents" / "Life-Index"
index_dir = data_dir / ".index"
journals_dir = data_dir / "Journals"

# 1. Count actual journal files
actual_md = list(journals_dir.rglob("*.md"))
actual_count = len(actual_md)
print(f"=== JOURNAL FILES ===")
print(f"Actual .md files in Journals/: {actual_count}")

# Collect all actual paths
actual_paths = set()
for md in actual_md:
    actual_paths.add(md.relative_to(data_dir).as_posix())

# 2. FTS index stats
fts_db = index_dir / "journals_fts.db"
if fts_db.exists():
    conn = sqlite3.connect(str(fts_db))
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM journals")
        fts_count = cur.fetchone()[0]
        print(f"\n=== FTS INDEX ===")
        print(f"FTS entries: {fts_count}")
        print(f"Actual files: {actual_count}")
        print(f"Delta: {fts_count - actual_count:+d}")
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print(f"Tables: {tables}")
        
        # Date range
        cur.execute("SELECT MIN(date), MAX(date) FROM journals")
        dr = cur.fetchone()
        print(f"Date range: {dr[0]} to {dr[1]}")
        
        # Check for duplicates
        cur.execute("SELECT path, COUNT(*) as cnt FROM journals GROUP BY path HAVING cnt > 1 LIMIT 5")
        dupes = cur.fetchall()
        if dupes:
            print(f"\nDUPLICATE PATHS in FTS: {len(dupes)} groups")
            for d in dupes[:3]:
                print(f"  Dupe: ...{d[0][-60:]} x{d[1]}")
        else:
            print("No duplicate paths in FTS")
        
        # Check for stale entries (in index but not on disk)
        cur.execute("SELECT path FROM journals")
        indexed_paths = set(r[0] for r in cur.fetchall())
        stale = indexed_paths - actual_paths
        missing = actual_paths - indexed_paths
        print(f"\nIn FTS but not on disk: {len(stale)}")
        if stale:
            for s in list(stale)[:3]:
                print(f"  Stale: {s[-60:]}")
        print(f"On disk but not in FTS: {len(missing)}")
        if missing:
            for m in list(missing)[:3]:
                print(f"  Missing: {m[-60:]}")
                
    except Exception as e:
        print(f"FTS error: {e}")
    conn.close()

# 3. Vector index stats
vec_pkl = index_dir / "vectors_simple.pkl"
vec_meta = index_dir / "vectors_simple_meta.json"
if vec_pkl.exists():
    print(f"\n=== VECTOR INDEX ===")
    with open(vec_pkl, "rb") as f:
        vec_data = pickle.load(f)
    if isinstance(vec_data, tuple) and len(vec_data) == 2:
        paths, embeddings = vec_data
        print(f"Type: tuple(paths, embeddings)")
        print(f"Paths count: {len(paths)}")
        if hasattr(embeddings, "shape"):
            print(f"Embeddings shape: {embeddings.shape}")
        vec_paths = set()
        for p in paths:
            if isinstance(p, str):
                # Normalize path
                vec_paths.add(p.replace("\\", "/"))
        print(f"Unique paths in vectors: {len(vec_paths)}")
        
        # Compare with actual
        vec_stale = vec_paths - actual_paths
        vec_missing = actual_paths - vec_paths
        print(f"In vectors but not on disk: {len(vec_stale)}")
        print(f"On disk but not in vectors: {len(vec_missing)}")
    elif isinstance(vec_data, dict):
        print(f"Type: dict")
        print(f"Keys: {list(vec_data.keys())[:10]}")
        for k, v in list(vec_data.items())[:3]:
            if hasattr(v, "shape"):
                print(f"  {k}: shape={v.shape}")
            elif isinstance(v, list):
                print(f"  {k}: list len={len(v)}")
            else:
                print(f"  {k}: type={type(v).__name__}")
    else:
        print(f"Type: {type(vec_data).__name__}")

if vec_meta.exists():
    meta = json.loads(vec_meta.read_text())
    print(f"\nVector meta: {json.dumps(meta, indent=2)}")

# 4. Empty DB files
print(f"\n=== EMPTY FILES ===")
for f in index_dir.iterdir():
    if f.is_file() and f.stat().st_size == 0:
        print(f"  EMPTY: {f.name}")

# 5. Index freshness
print(f"\n=== INDEX FRESHNESS ===")
now = datetime.now()
for f in index_dir.iterdir():
    if f.is_file() and f.stat().st_size > 0:
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        age_h = (now - mtime).total_seconds() / 3600
        size_kb = f.stat().st_size / 1024
        print(f"  {f.name}: {size_kb:.0f} KB, {age_h:.1f}h ago")
