"""CI gate. Block PRs that drop nDCG@10 by more than the configured delta.

Usage:
    python -m comps.eval.gate --baseline baseline.json --candidate candidate.json \\
        --min-ndcg-delta -0.01
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--candidate", type=Path, required=True)
    p.add_argument(
        "--min-ndcg-delta",
        type=float,
        default=-0.01,
        help="Minimum allowed change in mean_ndcg. Negative = tolerated regression.",
    )
    args = p.parse_args()

    base = json.loads(args.baseline.read_text())
    cand = json.loads(args.candidate.read_text())
    delta = cand["mean_ndcg"] - base["mean_ndcg"]

    status = "PASS" if delta >= args.min_ndcg_delta else "FAIL"
    print(
        f"baseline nDCG@10={base['mean_ndcg']:.3f} "
        f"candidate nDCG@10={cand['mean_ndcg']:.3f} "
        f"delta={delta:+.3f} "
        f"threshold={args.min_ndcg_delta:+.3f} "
        f"[{status}]"
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
