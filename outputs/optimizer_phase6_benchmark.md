# Phase 6 fair GA vs QIEA benchmark

## Controlled protocol

- Same deterministic feasible seed, improved by one shared coordinate-descent sweep.
- QIEA mean-field initialization disabled for this head-to-head.
- Both solvers retain their normal final coordinate-descent polish.
- 9 paired runs: 3 scenarios × 3 seeds.

## Result

QIEA wins: 3; GA wins: 6; ties: 0.
Median QIEA − GA cost: $283,659.32.
All runs feasible: True.

## Exact small instance

Exhaustive optimum: $821,986.85; GA gap: $0.00; QIEA gap: $0.00.

## Bounded claim

This controlled synthetic benchmark does not establish a material QIEA delivery-cost advantage unless repeated paired runs show one.
