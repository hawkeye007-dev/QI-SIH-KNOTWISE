"""Compliance domain logic — consumes `knotwise.regulatory` constants.

Scope-gating (Task 2, PLAN.md §3.4/§5.4/Phase 4) decides which regimes apply to
a vessel and at what voyage share. The compliance *ledger* (banking, borrowing,
pooling balances — the rest of Phase 4) is a separate, later concern: it
decides whether a vessel that a regime applies to is actually compliant, not
whether the regime applies in the first place.
"""
