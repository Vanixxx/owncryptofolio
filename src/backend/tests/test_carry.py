"""Loss carry of § 23 (ADR 0045)."""

from decimal import Decimal

from app.modules.tax.carry import rows
from app.modules.tax.report import limit_23

D = Decimal


def by_year(nets, fixed=None, until=2026):
    return {r["year"]: r for r in rows(nets, fixed or {}, limit_23, until)}


def test_a_loss_goes_back_one_year_into_a_taxed_gain_and_the_rest_forward():
    r = by_year({2022: D(1500), 2023: D(-2000), 2024: D(1200)}, until=2024)
    # 2023: 1,500 back into 2022 (taxed, over 600), 500 forward
    assert (r[2022]["back_in"], r[2022]["remaining"]) == (D(1500), D(0))
    assert (r[2023]["back_out"], r[2023]["loss"], r[2023]["end"]) == (D(1500), D(500), D(500))
    # 2024: 1,200 reaches the 1,000 limit → the carry of 500 is used
    assert (r[2024]["start"], r[2024]["used"], r[2024]["remaining"]) == (D(500), D(500), D(700))
    assert r[2024]["end"] == 0


def test_a_gain_below_the_limit_does_not_eat_the_carry():
    r = by_year({2023: D(-800), 2024: D(900), 2025: D(2000)}, until=2025)
    assert (r[2024]["taxable"], r[2024]["used"], r[2024]["end"]) == (False, D(0), D(800))
    assert (r[2025]["used"], r[2025]["remaining"]) == (D(800), D(1200))


def test_no_carry_back_into_a_year_below_the_limit():
    r = by_year({2023: D(500), 2024: D(-300)}, until=2024)
    assert r[2024]["back_out"] == 0 and r[2024]["end"] == D(300)


def test_the_assessed_figure_wins_and_shows_the_difference():
    r = by_year({2023: D(-800), 2024: D(-100), 2025: D(5000)}, {2023: (D(1000), "Bescheid")}, 2025)
    assert (r[2023]["end"], r[2023]["assessed"], r[2023]["diff"]) == (D(800), D(1000), D(200))
    assert r[2024]["start"] == D(1000) and r[2025]["used"] == D(1100)


def test_carry_from_before_the_first_year():
    r = by_year({2022: D(2000)}, {2021: (D(700), None)}, 2022)
    assert (r[2022]["start"], r[2022]["used"], r[2022]["remaining"]) == (D(700), D(700), D(1300))


def test_carry_api_and_report(authed):
    assert authed.put("/api/tax/carry/2020", json={"amount": "-1"}).status_code == 400
    assert (
        authed.put(
            "/api/tax/carry/2020", json={"amount": "250", "note": "Bescheid 2020"}
        ).status_code
        == 204
    )
    assert authed.put("/api/tax/carry/2020", json={"amount": None}).status_code == 204
