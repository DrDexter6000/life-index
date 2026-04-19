#!/usr/bin/env python3
"""Diagnose FTS index pollution - the real database."""
import sqlite3, os, json

idx_dir = os.path.expanduser("~/Documents/Life-Index/.index/")

fts_db = os.path.join(idx_dir, "journals_fts.db")
print(f"=== journals_fts.db ({os.path.getsize(fts_db)} bytes) ===\n")
conn = sqlite3.connect(fts_db)
cur = conn.cursor()

cur.execute("SELECT name, type FROM sqlite_master")
objects = cur.fetchall()
print("Database objects:")
for o in objects:
    print(f"  {o[1]}: {o[0]}")

tables = [o[0] for o in objects if o[1] == "table"]
for tbl in tables:
    cur.execute(f"PRAGMA table_info([{tbl}])")
    cols = cur.fetchall()
    cur.execute(f"SELECT COUNT(*) FROM [{tbl}]")
    count = cur.fetchone()[0]
    print(f"\n--- {tbl} ({count} rows) ---")
    for c in cols:
        print(f"  col[{c[0]}]: {c[1]} ({c[2]})")

print("\n\n========== POLLUTION ANALYSIS ==========\n")

# Use the journals table
for tbl in tables:
    cur.execute(f"PRAGMA table_info([{tbl}])")
    cols = [c[1] for c in cur.fetchall()]
    print(f"Table {tbl}: columns = {cols}")
    
    # Check each column for pytest paths
    for col in cols:
        try:
            cur.execute(f"SELECT COUNT(*) FROM [{tbl}] WHERE [{col}] LIKE '%pytest%'")
            cnt = cur.fetchone()[0]
            if cnt > 0:
                print(f"  ** {col} has {cnt} polluted entries!")
                cur.execute(f"SELECT [{col}] FROM [{tbl}] WHERE [{col}] LIKE '%pytest%' LIMIT 3")
                for r in cur.fetchall():
                    print(f"    POLLUTED: {str(r[0])[:150]}")
        except:
            pass

# FTS5 search test
print(f"\n=== FTS5 SEARCH TESTS ===")
for tbl in tables:
    if "fts" in tbl.lower() or "content" in tbl.lower():
        try:
            cur.execute(f"SELECT * FROM [{tbl}] WHERE [{tbl}] MATCH '团团' LIMIT 3")
            results = cur.fetchall()
            print(f"FTS5 MATCH '团团' in {tbl}: {len(results)} results")
            for r in results:
                print(f"  {str(r)[:200]}")
        except Exception as e:
            print(f"FTS5 MATCH error in {tbl}: {e}")

conn.close()

# index_manifest
manifest_path = os.path.join(idx_dir, "index_manifest.json")
if os.path.exists(manifest_path):
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    print(f"\n=== index_manifest.json ===")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))

# Real journal count
journals_dir = os.path.expanduser("~/Documents/Life-Index/Journals/")
real_count = sum(1 for root, dirs, files in os.walk(journals_dir) 
                 for f in files if f.endswith(".md") and "life-index_" in f)
print(f"\n=== Real journal files on disk: {real_count} ===")
