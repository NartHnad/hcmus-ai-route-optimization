# BENCHMARK_FINDINGS.md

Findings during the benchmark run.
**Do NOT modify algorithm implementations** without team review.

## Finding 1

| Field | Value |
|-------|-------|
| Algorithm | `BeamSearch` |
| File | `src/algorithms/beam_search.py` |
| Function | `beam_search` |
| Scenario | `ALL` |
| Observed | edge.calculate_cost(mode=mode) at lines 75,110. Edge.calculate_cost() has no 'mode' param. |
| Expected | edge.calculate_cost() without mode kwarg |
| Possible Cause | beam_search.py was written assuming Edge supports a mode str. Fix: remove mode=mode from both call sites. |

