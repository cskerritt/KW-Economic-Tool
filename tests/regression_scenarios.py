"""Scenario matrix for the calculation-regression battery.

Each scenario is a named, canonical (DECIMAL-rate) input dict for one module.
The same list drives three things, so they can never drift apart:

* ``generate_regression_baseline.py`` computes every scenario and freezes the
  full result (summary + every row/item) into ``regression_baseline.json``.
* ``test_regression_snapshot.py`` recomputes and deep-compares against that
  frozen baseline -- this is the "no calculation regression" guarantee.
* ``test_export_accuracy.py`` exports each scenario and parses the numbers back
  out of the xlsx/docx/pdf to confirm what a user downloads matches the engine.

These scenarios lock in *current, verified* output. The source-document accuracy
anchors (e.g. the Tinari $858,384.39 golden) live in the per-module unit tests
and are also represented here (see ``earn-exposito-golden``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    id: str
    module: str          # "earnings" | "lcp" | "lhhs"
    inputs: dict


# --- earnings ---------------------------------------------------------------

def _earn(**over) -> dict:
    base = dict(
        case_type="WD",
        base_earnings=80000.0, base_year=2015,
        start_year=2016, end_year=2035, valuation_year=2020,
        growth_past=0.03, growth_future=0.035, growth_switch_year=2021,
        discount_rate=0.04, worklife=0.90, unemployment=0.04,
        tax=0.15, fringe=0.0,
        pc_initial=0.0, pc_later=None, pc_switch_year=None,
        partial_years={},
    )
    base.update(over)
    return base


def _earnings_scenarios() -> list[Scenario]:
    s: list[Scenario] = []

    # The Tinari worked example (locks the $858,384.39 source-document golden).
    s.append(Scenario("earn-exposito-golden", "earnings", dict(
        case_type="WD", base_earnings=93628.0, base_year=2008,
        start_year=2009, end_year=2022, valuation_year=2015,
        growth_past=0.031, growth_future=0.038, growth_switch_year=2016,
        discount_rate=0.0325, worklife=0.919, unemployment=0.035,
        tax=0.12, fringe=0.0, pc_initial=0.25, pc_later=0.20,
        pc_switch_year=2016, partial_years={"2009": 0.33, "2022": 0.26},
    )))

    s.append(Scenario("earn-base", "earnings", _earn()))

    for d in (0.02, 0.03, 0.05, 0.06):
        s.append(Scenario(f"earn-discount-{d}", "earnings", _earn(discount_rate=d)))
    for w in (0.70, 0.80, 0.95, 1.00):
        s.append(Scenario(f"earn-worklife-{w}", "earnings", _earn(worklife=w)))
    for t in (0.0, 0.10, 0.20, 0.30):
        s.append(Scenario(f"earn-tax-{t}", "earnings", _earn(tax=t)))
    for f in (0.15, 0.25):
        s.append(Scenario(f"earn-fringe-{f}", "earnings", _earn(fringe=f)))
    for u in (0.0, 0.07, 0.12):
        s.append(Scenario(f"earn-unemp-{u}", "earnings", _earn(unemployment=u)))

    # Wrongful-death personal-consumption (flat and stepped).
    for pc in (0.20, 0.25, 0.33):
        s.append(Scenario(f"earn-pc-flat-{pc}", "earnings", _earn(pc_initial=pc)))
    s.append(Scenario("earn-pc-step", "earnings",
                      _earn(pc_initial=0.30, pc_later=0.22, pc_switch_year=2025)))

    # Growth regimes.
    for gp, gf in ((0.02, 0.02), (0.04, 0.03), (0.05, 0.06)):
        s.append(Scenario(f"earn-growth-{gp}-{gf}", "earnings",
                          _earn(growth_past=gp, growth_future=gf)))

    # Partial first/last years.
    s.append(Scenario("earn-partial-years", "earnings",
                      _earn(partial_years={"2016": 0.5, "2035": 0.4})))

    # Timeline shapes.
    s.append(Scenario("earn-all-future", "earnings",
                      _earn(valuation_year=2015)))               # every year discounted
    s.append(Scenario("earn-all-past", "earnings",
                      _earn(valuation_year=2040)))               # nothing discounted
    s.append(Scenario("earn-short", "earnings",
                      _earn(start_year=2016, end_year=2018)))
    s.append(Scenario("earn-long", "earnings",
                      _earn(end_year=2055)))
    s.append(Scenario("earn-fringe-and-pc", "earnings",
                      _earn(fringe=0.20, pc_initial=0.25)))
    # First loss year equals the base year (current-year injury): the base-year
    # gross must equal base_earnings (zero growth periods), not crash.
    s.append(Scenario("earn-start-equals-base", "earnings",
                      _earn(base_year=2020, start_year=2020, end_year=2035,
                            growth_switch_year=2026, valuation_year=2025)))
    # Discounting modes (lock the non-standard totals against regression).
    for m in ("nominal", "offset_zero", "offset_match"):
        s.append(Scenario(f"earn-mode-{m}", "earnings", _earn(discount_mode=m)))

    # Personal-injury dual stream: total disability + partial residual capacity.
    def _pi(resid_base, **over):
        base = _earn(case_type="PI", **over)
        if resid_base is None:
            base["residual"] = {}
        else:
            base["residual"] = dict(
                base_earnings=resid_base, worklife=0.85,
                unemployment=0.05, tax=0.10,
            )
        return base

    s.append(Scenario("earn-pi-total-disability", "earnings", _pi(None)))
    for rb in (20000.0, 40000.0, 60000.0):
        s.append(Scenario(f"earn-pi-residual-{int(rb)}", "earnings", _pi(rb)))
    s.append(Scenario("earn-pi-residual-highdiscount", "earnings",
                      _pi(40000.0, discount_rate=0.06)))
    s.append(Scenario("earn-pi-residual-fringe", "earnings",
                      _pi(40000.0, fringe=0.18)))
    # PI matching the unit-test golden (pre $1,106,012.93 / net $665,991.33).
    s.append(Scenario("earn-pi-exposito-golden", "earnings", dict(
        case_type="PI", base_earnings=93628.0, base_year=2008,
        start_year=2009, end_year=2022, valuation_year=2015,
        growth_past=0.031, growth_future=0.038, growth_switch_year=2016,
        discount_rate=0.0325, worklife=0.919, unemployment=0.035,
        tax=0.12, fringe=0.0, partial_years={"2009": 0.33, "2022": 0.26},
        residual={"base_earnings": 40000.0, "worklife": 0.85,
                  "unemployment": 0.05, "tax": 0.10},
    )))

    return s


# --- life care plan ---------------------------------------------------------

def _item(**over) -> dict:
    base = dict(
        name="Item", category="General", cost_per_unit=1000.0,
        start_year=2026, end_year=2046, growth_rate=0.03, base_year=2026,
        units_per_year=1.0,
    )
    base.update(over)
    return base


def _lcp(items, *, discount_rate=0.03, valuation_year=2025) -> dict:
    return dict(discount_rate=discount_rate, valuation_year=valuation_year, items=items)


def _lcp_scenarios() -> list[Scenario]:
    s: list[Scenario] = []

    s.append(Scenario("lcp-single-recurring", "lcp", _lcp([
        _item(name="Physician visits", category="Physician",
              cost_per_unit=200.0, units_per_year=4, growth_rate=0.04),
    ])))
    s.append(Scenario("lcp-single-replacement", "lcp", _lcp([
        _item(name="Wheelchair", category="DME", cost_per_unit=3000.0,
              end_year=2056, replacement_years=5, growth_rate=0.03),
    ])))
    s.append(Scenario("lcp-mixed-three", "lcp", _lcp([
        _item(name="Physician visits", category="Physician",
              cost_per_unit=200.0, units_per_year=4, growth_rate=0.04,
              end_year=2028),
        _item(name="Wheelchair", category="DME", cost_per_unit=3000.0,
              end_year=2036, replacement_years=5, growth_rate=0.03),
        _item(name="Home health aide", category="Attendant care",
              cost_per_unit=50000.0, end_year=2027, growth_rate=0.035,
              overlaps_household=True),
    ])))
    s.append(Scenario("lcp-with-overlap", "lcp", _lcp([
        _item(name="Therapy", category="Therapy", cost_per_unit=120.0,
              units_per_year=52, growth_rate=0.035, end_year=2040),
        _item(name="Attendant care", category="Attendant care",
              cost_per_unit=40000.0, units_per_year=1, growth_rate=0.04,
              end_year=2060, overlaps_household=True),
    ])))

    # Discount-rate sweep on a fixed item set.
    items = [
        _item(name="Meds", category="Pharmacy", cost_per_unit=300.0,
              units_per_year=12, growth_rate=0.045, end_year=2050),
        _item(name="Imaging", category="Diagnostics", cost_per_unit=1500.0,
              end_year=2050, replacement_years=3, growth_rate=0.03),
    ]
    for d in (0.02, 0.03, 0.04, 0.05, 0.06):
        s.append(Scenario(f"lcp-discount-{d}", "lcp",
                          _lcp(items, discount_rate=d)))

    # Growth-rate sweep on a single recurring item.
    for g in (0.0, 0.02, 0.04, 0.06):
        s.append(Scenario(f"lcp-growth-{g}", "lcp", _lcp([
            _item(name="Visits", category="Physician", cost_per_unit=250.0,
                  units_per_year=6, growth_rate=g, end_year=2045),
        ])))

    # Replacement cycles.
    for cyc in (2, 5, 10):
        s.append(Scenario(f"lcp-replace-{cyc}yr", "lcp", _lcp([
            _item(name="Equipment", category="DME", cost_per_unit=8000.0,
                  end_year=2066, replacement_years=cyc, growth_rate=0.03),
        ])))

    # Valuation-year shapes.
    s.append(Scenario("lcp-future-valuation", "lcp", _lcp([
        _item(name="Visits", category="Physician", cost_per_unit=250.0,
              units_per_year=6, growth_rate=0.04, end_year=2045),
    ], valuation_year=2026)))
    s.append(Scenario("lcp-late-valuation", "lcp", _lcp([
        _item(name="Visits", category="Physician", cost_per_unit=250.0,
              units_per_year=6, growth_rate=0.04, start_year=2026,
              end_year=2045),
    ], valuation_year=2035)))

    # Many categories.
    for m in ("nominal", "offset_zero", "offset_match"):
        s.append(Scenario(f"lcp-mode-{m}", "lcp", dict(_lcp([
            _item(name="Visits", category="Physician", cost_per_unit=250.0,
                  units_per_year=6, growth_rate=0.04, base_year=2024,
                  end_year=2045),
        ]), discount_mode=m)))

    s.append(Scenario("lcp-many-categories", "lcp", _lcp([
        _item(name="MD", category="Physician", cost_per_unit=220.0,
              units_per_year=4, growth_rate=0.04, end_year=2050),
        _item(name="PT", category="Therapy", cost_per_unit=130.0,
              units_per_year=40, growth_rate=0.035, end_year=2040),
        _item(name="Rx", category="Pharmacy", cost_per_unit=180.0,
              units_per_year=12, growth_rate=0.05, end_year=2055),
        _item(name="DME", category="DME", cost_per_unit=5000.0,
              end_year=2055, replacement_years=5, growth_rate=0.03),
        _item(name="Surgery", category="Surgical", cost_per_unit=60000.0,
              end_year=2046, replacement_years=20, growth_rate=0.045),
    ])))

    return s


# --- loss of household services ---------------------------------------------

def _stage(**over) -> dict:
    base = dict(start_year=2026, end_year=2040, weekly_hours=20.0,
                hourly_value=15.0, loss_percent=0.5)
    base.update(over)
    return base


def _lhhs(stages, *, base_year=2026, valuation_year=2025, growth_rate=0.03,
          discount_rate=0.03, area_wage_factor=1.0, self_consumption=0.0) -> dict:
    return dict(base_year=base_year, valuation_year=valuation_year,
                growth_rate=growth_rate, discount_rate=discount_rate,
                area_wage_factor=area_wage_factor, self_consumption=self_consumption,
                stages=stages)


def _lhhs_scenarios() -> list[Scenario]:
    s: list[Scenario] = []

    s.append(Scenario("lhhs-single-stage", "lhhs", _lhhs([_stage()])))
    s.append(Scenario("lhhs-two-stages", "lhhs", _lhhs([
        _stage(start_year=2026, end_year=2030, weekly_hours=20, loss_percent=0.5),
        _stage(start_year=2031, end_year=2045, weekly_hours=25, loss_percent=1.0),
    ])))
    s.append(Scenario("lhhs-three-stages", "lhhs", _lhhs([
        _stage(start_year=2026, end_year=2030, weekly_hours=30, loss_percent=0.4),
        _stage(start_year=2031, end_year=2040, weekly_hours=22, loss_percent=0.6),
        _stage(start_year=2041, end_year=2055, weekly_hours=15, loss_percent=1.0),
    ])))

    for d in (0.02, 0.03, 0.04, 0.05):
        s.append(Scenario(f"lhhs-discount-{d}", "lhhs",
                          _lhhs([_stage()], discount_rate=d)))
    for g in (0.0, 0.02, 0.04):
        s.append(Scenario(f"lhhs-growth-{g}", "lhhs",
                          _lhhs([_stage()], growth_rate=g)))
    for awf in (0.85, 0.936, 1.0, 1.12):
        s.append(Scenario(f"lhhs-area-{awf}", "lhhs",
                          _lhhs([_stage()], area_wage_factor=awf)))
    for sc in (0.0, 0.15, 0.30):
        s.append(Scenario(f"lhhs-selfconsume-{sc}", "lhhs",
                          _lhhs([_stage()], self_consumption=sc)))
    for lp in (0.25, 0.5, 0.75, 1.0):
        s.append(Scenario(f"lhhs-losspct-{lp}", "lhhs",
                          _lhhs([_stage(loss_percent=lp)])))

    s.append(Scenario("lhhs-all-future", "lhhs",
                      _lhhs([_stage()], valuation_year=2025)))
    s.append(Scenario("lhhs-late-valuation", "lhhs",
                      _lhhs([_stage(start_year=2026, end_year=2050)],
                            valuation_year=2035)))
    for m in ("nominal", "offset_zero", "offset_match"):
        s.append(Scenario(f"lhhs-mode-{m}", "lhhs",
                          dict(_lhhs([_stage()]), discount_mode=m)))

    s.append(Scenario("lhhs-full-combo", "lhhs", _lhhs([
        _stage(start_year=2026, end_year=2035, weekly_hours=28,
               hourly_value=16.5, loss_percent=0.6),
        _stage(start_year=2036, end_year=2050, weekly_hours=20,
               hourly_value=16.5, loss_percent=1.0),
    ], area_wage_factor=0.936, self_consumption=0.20, growth_rate=0.032,
       discount_rate=0.045)))

    return s


SCENARIOS: list[Scenario] = (
    _earnings_scenarios() + _lcp_scenarios() + _lhhs_scenarios()
)

# Stable lookup for parametrized tests.
BY_ID = {sc.id: sc for sc in SCENARIOS}

assert len(BY_ID) == len(SCENARIOS), "duplicate scenario id"
