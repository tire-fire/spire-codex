"""Backfill data/runs/*.json into the run_blobs collection. Idempotent,
resumable, leaves the files untouched.

    python -m scripts.backfill_run_blobs
"""

import argparse
import json
import os
import time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=500)
    args = ap.parse_args()
    if not os.environ.get("MONGO_URL", "").strip():
        print("MONGO_URL unset; nothing to do")
        return 1
    from app.services.runs_db_mongo import _blob_collection

    runs_dir = Path(os.environ.get("DATA_DIR", "data")) / "runs"
    files = sorted(runs_dir.glob("*.json"))
    print(f"{len(files)} run files under {runs_dir}", flush=True)
    coll = _blob_collection()
    inserted = skipped = failed = 0
    started = time.time()
    for i in range(0, len(files), args.batch):
        batch = files[i : i + args.batch]
        ids = [f.stem for f in batch]
        existing = {d["_id"] for d in coll.find({"_id": {"$in": ids}}, {"_id": 1})}
        docs = []
        for f in batch:
            if f.stem in existing:
                skipped += 1
                continue
            try:
                docs.append(
                    {"_id": f.stem, "blob": json.loads(f.read_text(encoding="utf-8"))}
                )
            except Exception as e:
                print(f"unreadable {f.name}: {e}", flush=True)
                failed += 1
        if docs:
            try:
                coll.insert_many(docs, ordered=False)
                inserted += len(docs)
            except Exception:
                for d in docs:
                    try:
                        coll.replace_one({"_id": d["_id"]}, d, upsert=True)
                        inserted += 1
                    except Exception as e:
                        print(f"failed {d['_id']}: {e}", flush=True)
                        failed += 1
        if (i // args.batch) % 40 == 0:
            done = i + len(batch)
            rate = done / max(time.time() - started, 1)
            print(
                f"{done}/{len(files)} files | {inserted} inserted, "
                f"{skipped} skipped, {failed} failed | {rate:.0f} files/s",
                flush=True,
            )
    print(
        f"done: {inserted} inserted, {skipped} skipped, {failed} failed "
        f"in {time.time() - started:.0f}s",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
