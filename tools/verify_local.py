from pathlib import Path
import sqlite3, shutil
root=Path(__file__).resolve().parents[1]
if not (root/"db.sqlite3").is_file():
    raise SystemExit("Missing database: refusing to create an empty corpus")
c=sqlite3.connect((root/"db.sqlite3").as_uri()+"?mode=ro",uri=True)
clips=c.execute("select audio from clips_clip").fetchall()
prompts=c.execute("select count(*) from reading_prompt").fetchone()[0]
if not clips or not prompts:
    raise SystemExit("Corpus is empty: check working folder and database")
missing=[a for a, in clips if not (root/"media"/a).is_file()]
if missing: raise SystemExit(f"Missing media: {len(missing)}")
print(f"Database: {root / 'db.sqlite3'}; clips: {len(clips)}; prompts: {prompts}; media OK")
