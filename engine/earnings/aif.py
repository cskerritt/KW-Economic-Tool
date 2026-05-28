"""The Adjusted Income Factor (AIF) of the Tinari algebraic method.

Source: Frank D. Tinari, "Demonstrating Lost Earnings: Algebraic vs.
Spreadsheet Method," The Earnings Analyst, Vol. 15, 2016.

Base form (no fringe benefits):

    AIF = { [ (GE x WLE)(1 - UF) ] (1 - TL) } (1 - PC)

With fringe benefits, taxes apply to wages only, not to the fringe portion:

    AIF = { [ (GE x WLE)(1 - UF) ](1 + FB) - [ (GE x WLE)(1 - UF) ](TL) } (1 - PC)

GE factors out, so the factor below is per dollar of gross earnings. Setting
FB = 0 reduces the fringe form to the base form.
"""

from __future__ import annotations


def adjusted_income_factor(
    worklife: float,
    unemployment: float,
    tax: float,
    personal_consumption: float,
    fringe: float = 0.0,
) -> float:
    """Return the per-dollar Adjusted Income Factor.

    Args:
        worklife: worklife-to-retirement ratio, WLE (e.g. 0.919).
        unemployment: unemployment factor, UF (e.g. 0.035).
        tax: effective income tax rate, TL (e.g. 0.12). Use 0.0 where the
            jurisdiction does not require a tax adjustment.
        personal_consumption: PC (e.g. 0.25). Use 0.0 for personal injury;
            personal consumption is deducted in wrongful death only.
        fringe: fringe benefit rate, FB (e.g. 0.06). Default 0.0.

    Returns:
        The factor to multiply gross earnings by to get adjusted income.
    """
    for name, value in (
        ("worklife", worklife),
        ("unemployment", unemployment),
        ("tax", tax),
        ("personal_consumption", personal_consumption),
        ("fringe", fringe),
    ):
        if value < 0:
            raise ValueError(f"{name} must be >= 0, got {value}")

    # Worklife-adjusted, then unemployment-adjusted, base (per dollar of GE).
    wage_base = worklife * (1.0 - unemployment)

    # Fringe is added to the wage base; income tax applies to the wage portion
    # only (not the fringe), per the paper's footnote 6.
    after_tax = wage_base * (1.0 + fringe) - wage_base * tax

    return after_tax * (1.0 - personal_consumption)
