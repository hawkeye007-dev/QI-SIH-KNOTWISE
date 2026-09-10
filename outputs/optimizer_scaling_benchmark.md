# Optimizer fleet-scaling probe

## Scope

Synthetic fleets repeat the documented class mix and proportionally scale annual cargo demand.
This is an end-to-end, fixed-budget timing probe. Quality beyond the one-slot exact case is relative to the best observed result at each size, not an optimality guarantee.

## Results

| Vessels | Decision slots | Solver | Median seconds | Best cost | Gap to best observed | Feasible |
| ---: | ---: | --- | ---: | ---: | ---: | --- |
| 10 | 50 | GA | 0.31 | $424,650,184 | 6.26% | True |
| 10 | 50 | QIEA | 0.46 | $399,636,955 | 0.00% | True |
| 25 | 125 | GA | 1.50 | $1,254,296,130 | 7.85% | True |
| 25 | 125 | QIEA | 1.82 | $1,163,043,058 | 0.00% | True |
| 50 | 250 | GA | 5.42 | $2,202,814,511 | 7.55% | True |
| 50 | 250 | QIEA | 6.04 | $2,048,096,749 | 0.00% | True |
| 100 | 500 | GA | 23.19 | $4,426,037,672 | 8.82% | True |
| 100 | 500 | QIEA | 25.22 | $4,067,314,089 | 0.00% | True |
| 200 | 1000 | GA | 112.18 | $8,927,956,707 | 8.87% | True |
| 200 | 1000 | QIEA | 111.66 | $8,200,792,026 | 0.00% | True |

## Bounded interpretation

This synthetic fixed-budget scaling probe measures feasibility, time and relative observed quality. It does not establish an operational QIEA advantage or an exact optimality gap beyond the enumerated one-slot reference.
