"""Backfill data/runs/*.json into the run_blobs collection. Idempotent,
resumable, leaves the files untouched. Also runs automatically in the
rebuilder on its first refresh-lease cycle; this wrapper is for manual runs.

    python -m scripts.backfill_run_blobs
"""

import argparse
import logging
import os


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=500)
    args = ap.parse_args()
    if not os.environ.get("MONGO_URL", "").strip():
        print("MONGO_URL unset; nothing to do")
        return 1
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from app.services.runs_db_mongo import backfill_run_blobs

    result = backfill_run_blobs(batch=args.batch)
    print(result, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
