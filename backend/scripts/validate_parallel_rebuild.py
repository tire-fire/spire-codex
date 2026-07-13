"""Prove the parallel snapshot rebuild is identical to the serial one.

Run inside the backend container against the real run data BEFORE enabling
parallel rebuilds:

    python -m scripts.validate_parallel_rebuild [workers]

It runs the full walk twice in one process — serial, then parallel — and deep-
compares the results (ints exact, floats within 1e-9). Because both finalize in
the same process, hash-seed-dependent set ordering matches, so the compare is
exact. Exit 0 + "IDENTICAL" means the parallel path is safe to turn on
(ENTITY_STATS_REBUILD_WORKERS=<workers>); a MISMATCH means do NOT enable it.

The `if __name__ == "__main__"` guard is required: the parallel path uses the
"spawn" start method, which re-imports this module in each worker.
"""

import os
import sys
import time


def _diff(x, y, path=""):
    if type(x) is not type(y):
        return [f"{path}: type {type(x).__name__} vs {type(y).__name__}"]
    if isinstance(x, dict):
        out = [f"{path}: keys ({len(x)} vs {len(y)})"] if set(x) != set(y) else []
        for k in x:
            if k in y:
                out += _diff(x[k], y[k], f"{path}.{k}")
        return out
    if isinstance(x, (list, tuple)):
        if len(x) != len(y):
            return [f"{path}: len {len(x)} vs {len(y)}"]
        # A list whose elements are themselves lists/tuples is a serialized
        # dict/set (e.g. charts cells), so it's order-independent — the parallel
        # merge builds it in a different order than the serial run, same data.
        # Sort both before comparing so only genuine value differences surface.
        # A list of scalars (e.g. per-act [n0, n1, n2]) is positional: compare
        # in place.
        if x and all(isinstance(e, (list, tuple)) for e in x):
            xs = sorted(x, key=repr)
            ys = sorted(y, key=repr)
        else:
            xs, ys = x, y
        out = []
        for i, (u, v) in enumerate(zip(xs, ys)):
            out += _diff(u, v, f"{path}[{i}]")
        return out
    if isinstance(x, float):
        return [] if abs(x - y) < 1e-9 else [f"{path}: {x} vs {y}"]
    return [] if x == y else [f"{path}: {x!r} vs {y!r}"]


def main() -> int:
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else (os.cpu_count() or 4)
    import app.services.run_entity_stats as r

    r._PARALLEL_MIN_RUNS = 1  # force the parallel path regardless of run count

    print("running serial rebuild...", flush=True)
    os.environ["ENTITY_STATS_REBUILD_WORKERS"] = "1"
    t0 = time.time()
    ser = r._build_cache_data()
    t_ser = time.time() - t0
    print(f"  serial: {len(ser[0])} entities in {t_ser:.1f}s", flush=True)

    print(f"running parallel rebuild ({workers} workers)...", flush=True)
    os.environ["ENTITY_STATS_REBUILD_WORKERS"] = str(workers)
    t0 = time.time()
    par = r._build_cache_data()
    t_par = time.time() - t0
    print(f"  parallel: {len(par[0])} entities in {t_par:.1f}s", flush=True)

    d = _diff(ser, par)
    print(f"\ndifferences: {len(d)}")
    for line in d[:30]:
        print("  ", line)
    if d:
        print("\nRESULT: MISMATCH — DO NOT enable parallel rebuilds")
        return 1
    speedup = t_ser / t_par if t_par else 0
    print(f"\nRESULT: IDENTICAL — parallel is safe ({speedup:.1f}x faster). Enable")
    print(f"with ENTITY_STATS_REBUILD_WORKERS={workers}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
