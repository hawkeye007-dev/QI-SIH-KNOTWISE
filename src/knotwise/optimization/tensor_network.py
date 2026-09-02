"""Generic Matrix Product State / Born-machine linear algebra.

Fleet-agnostic on purpose — no `knotwise.fleet` or `knotwise.regulatory`
imports here. This module is the actual mathematics PLAN.md §1.3 and §3.1
describe and DESIGN_NOTE_POOLING.md assumes exists: a real quantum-many-body
representation of a probability distribution, not a classically-flavoured
proxy that borrows the vocabulary.

Two operations, both textbook:

- `tt_svd` — the Tensor-Train / Matrix Product State decomposition
  (Oseledets 2011): sequential SVD sweeps that turn an n-dimensional array
  into a chain of 3-index cores. Exact when no `max_bond` truncation is
  requested (every singular value kept), which is this module's default —
  truncation only matters once the joint tensor is large enough to need
  compressing, which is explicitly out of scope for `mps_exposure.py`'s
  current per-vessel-year scale (see that module's docstring).
- `mutual_information` — PLAN §3.1's own definition, implemented literally:
  "mutual information between two subsystems of a quantum state ... obtained
  here from the singular value spectrum at the relevant bond." Given a joint
  probability tensor, this builds the Born-machine amplitude state
  `ψ = sqrt(P)` (Han et al. 2018 — the same object PLAN.md names throughout),
  which is a valid normalized quantum state in the computational basis
  because `Σ P = 1 ⇒ Σ ψ² = 1`, then computes `S(ρ_A) + S(ρ_B) − S(ρ_AB)`
  from the eigenvalues of the reduced density matrices obtained by
  contracting `ψψ†` down to each subsystem.
"""

from __future__ import annotations

import numpy as np

#: Floor below which a probability/eigenvalue is treated as exactly zero —
#: guards `log2(0)` and stray negative-epsilon eigenvalues from SVD/eigh
#: round-off, without meaningfully biasing the entropy of anything that
#: isn't already numerically negligible.
_EPSILON = 1e-12


def tt_svd(tensor: np.ndarray, max_bond: int | None = None) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Decompose an n-dimensional `tensor` into a chain of MPS cores via
    sequential SVD (Oseledets 2011).

    Returns `(cores, bond_singular_values)`:

    - `cores[i]` has shape `(left_bond, tensor.shape[i], right_bond)` (the
      first core's left bond and the last core's right bond are both 1).
      Contracting the full chain over the bond indices reproduces `tensor`
      exactly when `max_bond` is `None` (verified by
      `test_tensor_network.py`'s round-trip test) — this is a decomposition,
      not a fit.
    - `bond_singular_values[i]` is the singular-value vector at the i-th
      bond (between core i and core i+1), `len(cores) - 1` entries in total.
      These are exactly the Schmidt coefficients for the bipartition at that
      bond, and are what `von_neumann_entropy` and `mutual_information`
      consume.

    `max_bond`, if given, truncates each SVD to its top `max_bond` singular
    values — standard MPS bond-dimension truncation. Left `None` by every
    caller in this codebase today (see module docstring); implemented here
    because `mutual_information`'s reduced-density-matrix route does not
    need it, but a full-fleet-scale MPS (Track F) would.
    """
    if tensor.ndim < 1:
        raise ValueError("tt_svd requires at least a 1-dimensional tensor")

    shape = tensor.shape
    cores: list[np.ndarray] = []
    bond_singular_values: list[np.ndarray] = []

    # Running matrix: starts as the full tensor reshaped to (left_bond=1, rest).
    remainder = tensor.reshape(1, -1).astype(np.float64)
    left_bond = 1
    for mode_size in shape[:-1]:
        remainder = remainder.reshape(left_bond * mode_size, -1)
        u, s, vh = np.linalg.svd(remainder, full_matrices=False)
        if max_bond is not None and len(s) > max_bond:
            u, s, vh = u[:, :max_bond], s[:max_bond], vh[:max_bond, :]
        rank = len(s)
        cores.append(u.reshape(left_bond, mode_size, rank))
        bond_singular_values.append(s)
        remainder = np.diag(s) @ vh
        left_bond = rank
    cores.append(remainder.reshape(left_bond, shape[-1], 1))

    return cores, bond_singular_values


def reconstruct_from_cores(cores: list[np.ndarray]) -> np.ndarray:
    """Contract an MPS core chain back into a dense tensor — used by the
    round-trip test to confirm `tt_svd` is an exact decomposition, not an
    approximation, when called with `max_bond=None`."""
    result = cores[0]
    for core in cores[1:]:
        # result: (left, *modes_so_far, bond) ; core: (bond, mode, right)
        result = np.tensordot(result, core, axes=([-1], [0]))
    # Drop the leading/trailing bond-1 axes.
    return result.reshape(result.shape[1:-1])


def von_neumann_entropy(singular_values: np.ndarray) -> float:
    """Entanglement entropy `S = -Σ λ_i² log2(λ_i²)` of an MPS bond's Schmidt
    spectrum, where `singular_values` are the (already-normalized, i.e. from
    a state with `Σψ²=1`) singular values at that bond."""
    probs = np.asarray(singular_values, dtype=np.float64) ** 2
    probs = probs[probs > _EPSILON]
    if probs.size == 0:
        return 0.0
    return float(-np.sum(probs * np.log2(probs)))


def _reduced_density_matrix(psi: np.ndarray, keep_axes: tuple[int, ...]) -> np.ndarray:
    """`ρ = Tr_{other axes}(|ψ⟩⟨ψ|)` for the subsystem spanning `keep_axes`
    of the n-dimensional amplitude tensor `psi` — an exact partial trace via
    `einsum`, not an MPS-bond shortcut, so it works for any (including
    non-adjacent) subset of axes, which a strict 2-block MPS bond SVD cannot
    address directly once there are 3+ subsystems."""
    other_axes = tuple(ax for ax in range(psi.ndim) if ax not in keep_axes)
    # Bring kept axes to the front, others to the back, then flatten each
    # group so ψ becomes a (kept_dim, other_dim) matrix M; ρ = M @ M.conj().T.
    order = keep_axes + other_axes
    reshaped = np.transpose(psi, order).reshape(int(np.prod([psi.shape[a] for a in keep_axes])), -1)
    rho = reshaped @ reshaped.conj().T
    return rho


def _entropy_of_density_matrix(rho: np.ndarray) -> float:
    eigenvalues = np.linalg.eigvalsh(rho)
    eigenvalues = eigenvalues[eigenvalues > _EPSILON]
    if eigenvalues.size == 0:
        return 0.0
    return float(-np.sum(eigenvalues * np.log2(eigenvalues)))


def mutual_information(joint_probs: np.ndarray, axis_a: int, axis_b: int) -> float:
    """`I(A:B) = S(ρ_A) + S(ρ_B) − S(ρ_AB)` for the Born-machine state
    `ψ = sqrt(joint_probs)`, where A and B are the subsystems living on
    `axis_a` and `axis_b` of the (possibly higher-dimensional) tensor.

    `joint_probs` must be a non-negative array summing to 1 (a genuine
    probability tensor over every axis, not just the two of interest) —
    this is what makes `ψ` a normalized quantum state and the resulting
    quantity a real entanglement-entropy-based mutual information, not a
    renamed classical formula. Axes other than `axis_a`/`axis_b` are traced
    out exactly (`_reduced_density_matrix`), so correlations mediated
    through a third axis are correctly folded into `ρ_AB` before entropy is
    taken.

    Equivalent, for a strict two-block bipartition, to taking the entropy of
    `tt_svd`'s bond singular-value spectrum at that bond (`eigenvalues of
    ρ = AA^T` are exactly the squared singular values of the amplitude
    matrix `A`) — implemented here via direct eigendecomposition of the
    reduced density matrix instead, because that is what generalizes to the
    non-adjacent axis pairs `mps_exposure.py` needs (a bare MPS bond only
    ever bipartitions the chain into two contiguous halves).

    **A documented subtlety, not a bug:** when `axis_a`/`axis_b` are the
    *only* two axes in `joint_probs` (no other axis to trace out), `ρ_AB`
    is the full pure state and always has `S(ρ_AB) = 0`, which makes this
    reduce to `2·S(ρ_A)` for a deterministic A↔B relationship — not the
    classical Shannon `I(A;B) = H(A)`. This is standard quantum-information
    behaviour for a bipartite pure state, not a defect of this
    implementation, and `test_tensor_network.py` tests it explicitly rather
    than silently relying on it. It matches classical Shannon MI once a
    third "which-outcome" axis is present to purify the pair into a
    genuinely mixed `ρ_AB` (also tested) — which is the normal case for
    `mps_exposure.py`'s real, many-axis tensors, where every other decision
    field plays that role.
    """
    if axis_a == axis_b:
        raise ValueError("axis_a and axis_b must be different axes")
    total = float(np.sum(joint_probs))
    if not np.isclose(total, 1.0, atol=1e-6):
        raise ValueError(f"joint_probs must sum to 1 (got {total})")

    psi = np.sqrt(np.clip(joint_probs, 0.0, None))

    rho_a = _reduced_density_matrix(psi, (axis_a,))
    rho_b = _reduced_density_matrix(psi, (axis_b,))
    rho_ab = _reduced_density_matrix(psi, (axis_a, axis_b) if axis_a < axis_b else (axis_b, axis_a))

    return _entropy_of_density_matrix(rho_a) + _entropy_of_density_matrix(rho_b) - _entropy_of_density_matrix(rho_ab)
