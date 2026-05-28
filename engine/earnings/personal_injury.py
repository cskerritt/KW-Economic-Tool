"""Personal-injury earnings loss as pre-injury capacity minus residual capacity.

Per the locked methodology (see CLAUDE.md), a personal-injury loss is NOT a
wrongful-death loss with personal consumption set to zero on a single stream.
It is the difference between two earnings streams, each run through the same
Tinari algebraic method with personal consumption fixed at zero:

* pre-injury stream  - what the plaintiff would have earned but for the injury.
* residual stream    - what the plaintiff can still earn given the injury
                       (their post-injury residual earning capacity).

The annual loss is the pre-injury figure minus the residual figure; present
value is the sum of the per-year differences. Because both streams are
discounted at the same net rate over the same years, subtracting present values
year by year is identical to discounting the annual difference, so this stays a
pure linear composition of two audited engine runs.

Total disability is the special case where the residual stream is zero; then the
net loss equals the pre-injury stream. This makes the dual-stream result a strict
generalization of the previous single-stream PI behavior.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.earnings.projection import EarningsResult, YearResult


@dataclass
class PersonalInjuryResult:
    """Net PI loss with both component streams retained for the audit trail.

    ``rows``/``total_present_value``/``past_present_value``/
    ``future_present_value`` carry the NET (pre minus residual) figures, so this
    object renders, exports, and summarizes through the same code paths as a
    single-stream :class:`EarningsResult`. ``pre_injury`` and ``residual`` keep
    the underlying streams so a report can show the full derivation.
    """

    rows: list[YearResult]
    total_present_value: float
    past_present_value: float
    future_present_value: float
    pre_injury: EarningsResult
    residual: EarningsResult

    def aif_values(self) -> list[float]:
        """Distinct AIF values used by the pre-injury stream, in first-seen order."""
        seen: list[float] = []
        for r in self.rows:
            if r.aif not in seen:
                seen.append(r.aif)
        return seen


def project_personal_injury(
    pre_injury: EarningsResult,
    residual: EarningsResult,
) -> PersonalInjuryResult:
    """Combine a pre-injury and a residual stream into a net PI loss.

    Rows are aligned by year. A year present in the pre-injury stream but absent
    from the residual stream contributes its full pre-injury value (residual
    treated as zero for that year). The net per-year ``YearResult`` carries the
    pre-injury ``aif`` and ``portion`` for display and the differenced
    ``gross_earnings``, ``adjusted_income`` and ``present_value``.
    """
    residual_by_year = {r.year: r for r in residual.rows}

    rows: list[YearResult] = []
    past_pv = 0.0
    future_pv = 0.0
    for p in pre_injury.rows:
        r = residual_by_year.get(p.year)
        r_gross = r.gross_earnings if r is not None else 0.0
        r_adjusted = r.adjusted_income if r is not None else 0.0
        r_pv = r.present_value if r is not None else 0.0

        net_pv = p.present_value - r_pv
        rows.append(
            YearResult(
                year=p.year,
                portion=p.portion,
                gross_earnings=p.gross_earnings - r_gross,
                aif=p.aif,
                adjusted_income=p.adjusted_income - r_adjusted,
                present_value=net_pv,
                is_future=p.is_future,
            )
        )
        if p.is_future:
            future_pv += net_pv
        else:
            past_pv += net_pv

    return PersonalInjuryResult(
        rows=rows,
        total_present_value=past_pv + future_pv,
        past_present_value=past_pv,
        future_present_value=future_pv,
        pre_injury=pre_injury,
        residual=residual,
    )
