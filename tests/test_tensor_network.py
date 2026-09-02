"""Tests for the generic MPS / Born-machine linear algebra
(`knotwise.optimization.tensor_network`) — fleet-agnostic, no fixtures
beyond hand-built small tensors, so these stay fast and pin down the math
in isolation from `mps_exposure.py`'s fleet-facing construction."""

from __future__ import annotations

import numpy as np
import pytest

from knotwise.optimization.tensor_network import (
    mutual_information,
    reconstruct_from_cores,
    tt_svd,
    von_neumann_entropy,
)


def _classical_shannon_mi(joint: np.ndarray) -> float:
    """Direct classical `I(A;B) = Σ p(a,b) log2(p(a,b)/(p(a)p(b)))`, used
    only as an independent cross-check inside these tests — not imported by
    `tensor_network.py` itself."""
    p_a = joint.sum(axis=1, keepdims=True)
    p_b = joint.sum(axis=0, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(joint > 0, joint / (p_a * p_b), 1.0)
        terms = np.where(joint > 0, joint * np.log2(ratio), 0.0)
    return float(terms.sum())


class TestMutualInformationIndependence:
    def test_independent_uniform_variables_give_zero(self):
        rng = np.random.default_rng(0)
        p_a = rng.dirichlet(np.ones(3))
        p_b = rng.dirichlet(np.ones(4))
        joint = np.outer(p_a, p_b)
        assert joint.sum() == pytest.approx(1.0)

        mi = mutual_information(joint, axis_a=0, axis_b=1)
        assert mi == pytest.approx(0.0, abs=1e-9)

    def test_independent_variables_with_a_spectator_axis_still_zero(self):
        # Same independence check, but embedded in a 3-axis tensor (a
        # spectator axis C uncorrelated with A and B) -- confirms
        # independence still gives ~0 once other axes are present, which is
        # the shape `mps_exposure.py` actually uses (r + 6 fields).
        rng = np.random.default_rng(1)
        p_a = rng.dirichlet(np.ones(3))
        p_b = rng.dirichlet(np.ones(2))
        p_c = rng.dirichlet(np.ones(4))
        joint = np.einsum("a,b,c->abc", p_a, p_b, p_c)
        assert joint.sum() == pytest.approx(1.0)

        mi = mutual_information(joint, axis_a=0, axis_b=1)
        assert mi == pytest.approx(0.0, abs=1e-9)


class TestMutualInformationPureBipartiteDegeneracy:
    """Documents, rather than hides, the known pure-bipartite-state
    behaviour described in `mutual_information`'s own docstring: with only
    two axes in the tensor (nothing to trace out), a deterministic A<->B
    relationship gives `2*S(A)`, not the classical `H(A)`."""

    def test_bare_two_axis_bijection_gives_twice_the_marginal_entropy(self):
        n = 4
        joint = np.eye(n) / n  # P(a,b) = 1/n if a==b else 0
        mi = mutual_information(joint, axis_a=0, axis_b=1)
        marginal_entropy = np.log2(n)  # H(A) = H(B) = log2(n) for a uniform bijection
        assert mi == pytest.approx(2 * marginal_entropy, rel=1e-9)
        # And it's therefore *not* the classical Shannon MI of the same table.
        assert mi != pytest.approx(_classical_shannon_mi(joint), rel=1e-3)


class TestMutualInformationPurifiedClassicalDistribution:
    """The construction that *does* recover classical Shannon MI exactly:
    add a third "which-outcome" witness axis E so that tracing it out of the
    tripartite pure state reproduces the classical-classical correlated
    mixed state `rho_AB = sum_{a,b} P(a,b) |a,b><a,b|` -- the standard
    purification of a classical joint distribution. This is the same role
    `mps_exposure.py`'s other five decision-field axes play for any one
    field pair: enough extra structure that the reduced pair is genuinely
    mixed rather than degenerately pure."""

    def _purify(self, joint_ab: np.ndarray) -> np.ndarray:
        n_a, n_b = joint_ab.shape
        n_e = n_a * n_b
        psi = np.zeros((n_a, n_b, n_e))
        e = 0
        for a in range(n_a):
            for b in range(n_b):
                psi[a, b, e] = np.sqrt(joint_ab[a, b])
                e += 1
        return psi**2  # a valid joint probability tensor P(a, b, e)

    def test_matches_classical_shannon_mi_exactly(self):
        joint_ab = np.array([[0.10, 0.20, 0.05], [0.15, 0.05, 0.10], [0.05, 0.20, 0.10]])
        assert joint_ab.sum() == pytest.approx(1.0)

        joint_abe = self._purify(joint_ab)
        assert joint_abe.sum() == pytest.approx(1.0)

        mi = mutual_information(joint_abe, axis_a=0, axis_b=1)
        expected = _classical_shannon_mi(joint_ab)
        assert mi == pytest.approx(expected, rel=1e-6, abs=1e-9)


class TestTTSVDRoundTrip:
    def test_reconstructs_arbitrary_tensor_exactly_without_truncation(self):
        rng = np.random.default_rng(42)
        tensor = rng.random((3, 4, 2, 5))
        cores, bond_singular_values = tt_svd(tensor, max_bond=None)

        assert len(cores) == tensor.ndim
        assert len(bond_singular_values) == tensor.ndim - 1
        assert cores[0].shape[0] == 1
        assert cores[-1].shape[-1] == 1

        reconstructed = reconstruct_from_cores(cores)
        assert reconstructed.shape == tensor.shape
        assert np.allclose(reconstructed, tensor, atol=1e-8)

    def test_probability_tensor_bond_entropy_matches_reduced_density_matrix_route(self):
        # For a strict two-block bipartition (a 2-axis tensor), tt_svd's
        # single bond's singular values should give the same entropy as
        # mutual_information's direct reduced-density-matrix route for one
        # of the two marginals -- two different code paths, same math.
        rng = np.random.default_rng(7)
        p_a = rng.dirichlet(np.ones(3))
        p_b = rng.dirichlet(np.ones(3))
        joint = 0.5 * np.outer(p_a, p_b) + 0.5 * np.eye(3) / 3  # correlated, not independent

        psi = np.sqrt(joint)
        _, bond_singular_values = tt_svd(psi, max_bond=None)
        bond_entropy = von_neumann_entropy(bond_singular_values[0])

        # S(rho_A) via mutual_information's own machinery: I(A:B) for a bare
        # two-axis *pure* state reduces to 2*S(A) (see the degeneracy test
        # above), so S(A) = mutual_information(...) / 2.
        mi = mutual_information(joint, axis_a=0, axis_b=1)
        assert bond_entropy == pytest.approx(mi / 2, rel=1e-6, abs=1e-9)


class TestVonNeumannEntropy:
    def test_zero_for_a_single_certain_outcome(self):
        assert von_neumann_entropy(np.array([1.0])) == pytest.approx(0.0)

    def test_maximal_for_uniform_spectrum(self):
        n = 8
        uniform_singular_values = np.full(n, np.sqrt(1 / n))
        assert von_neumann_entropy(uniform_singular_values) == pytest.approx(np.log2(n))
