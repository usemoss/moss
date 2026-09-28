"""Drive moss_scale.py over doubling doc counts, halting before a projected memory blow-up.

Stop rule: halt if the linear projection of peak RSS from the last two sizes exceeds 75% of RAM,
or the per-doc RSS slope more than doubles between segments (worse than linear).
Run: MOSS_ENV_FILE=<.env> .venv/bin/python moss_ramp.py [max_docs]
"""

import re
import subprocess
import sys

from bench_local import HERE, MEM_LIMIT_MB, RESULTS

SIZES = [1_000, 2_000, 4_000, 8_000, 16_000, 32_000, 64_000, 100_000]
if len(sys.argv) > 1:
    SIZES = [n for n in SIZES if n <= int(sys.argv[1])]
peaks: list[tuple[int, float]] = []

for i, n in enumerate(SIZES):
    log = RESULTS / f"moss-scale-{n}.log"
    rc = subprocess.call(
        [
            str(HERE / "watchdog.sh"),
            str(log),
            str(HERE / ".venv/bin/python"),
            "moss_scale.py",
            str(n),
        ],
        cwd=HERE,
    )
    text = log.read_text()
    print(text.strip())
    if rc != 0:
        print(f"HALT: {n} docs exited rc={rc}")
        break
    peaks.append((n, float(re.search(r"peak RSS (\d+) MB", text).group(1))))
    if len(peaks) >= 2 and i + 1 < len(SIZES):
        (n1, p1), (n2, p2) = peaks[-2:]
        slope = (p2 - p1) / (n2 - n1)
        projected = p2 + slope * (SIZES[i + 1] - n2)
        print(
            f"  slope {slope:.3f} MB/doc -> projected peak at {SIZES[i + 1]}: {projected:.0f} MB"
        )
        if projected > MEM_LIMIT_MB:
            print(f"HALT: projection {projected:.0f} MB > {MEM_LIMIT_MB:.0f} MB")
            break
        if len(peaks) >= 3 and n2 >= 8_000:
            (n0, p0) = peaks[-3]
            prev = (p1 - p0) / (n1 - n0)
            if prev > 0 and slope > 2 * prev:
                print(f"HALT: slope grew {slope / prev:.1f}x (worse than linear)")
                break

print("\nsize,peak_rss_mb")
for n, p in peaks:
    print(f"{n},{p:.0f}")
