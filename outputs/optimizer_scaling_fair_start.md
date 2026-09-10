# Optimizer fleet-scaling probe

## Scope

Synthetic fleets repeat the documented class mix and proportionally scale annual cargo demand.
This is an end-to-end, fixed-budget timing probe. Quality beyond the one-slot exact case is relative to the best observed result at each size, not an optimality guarantee.

## Results

| Vessels | Decision slots | Solver | Median seconds | Best cost | Gap to best observed | Feasible |
| ---: | ---: | --- | ---: | ---: | ---: | --- |
| 100 | 500 | GA | 19.85 | $4,088,699,830 | 0.07% | True |
| 100 | 500 | QIEA | 21.48 | $4,085,991,685 | 0.00% | True |
| 200 | 1000 | GA | 87.01 | $8,174,322,526 | 0.01% | True |
| 200 | 1000 | QIEA | 86.93 | $8,173,279,143 | 0.00% | True |

## Bounded interpretation

This synthetic shared-start scaling check isolates solver behavior after one identical feasible anchor. It does not establish an exact optimality gap beyond the enumerated one-slot reference.
