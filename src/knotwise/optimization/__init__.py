"""Objective function, fuel model, compliance costs, pooling, and the
per-scenario GA solver (Task 2R component 3).

Consumes `knotwise.fleet` (component 2) and `knotwise.compliance.scope_gating`
plus `knotwise.regulatory` (Task 2 / Phase 0) — this package composes them
into a searchable objective, it does not redefine any of their concerns.
"""
