"""The deterministic context evals are a CI gate: every metric must stay on target."""

from evals.context_static import run_static_context_evals


async def test_static_context_evals_are_on_target() -> None:
    metrics = await run_static_context_evals()
    failing = [f"{m.name}={m.value:.3f} ({m.detail})" for m in metrics if not m.passed]
    assert not failing, "context regressions: " + "; ".join(failing)
