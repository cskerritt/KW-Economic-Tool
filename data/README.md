# Reference data (extracted from source PDFs)

CSVs scraped from the authoritative source documents. One CSV per table. Every
folder has an `_index.csv` listing its tables. Rates and dollar values are kept
exactly as printed in the source (not converted).

## Coverage

| Folder | Source | Tables | Notes |
|---|---|---|---|
| `sck_wle/` | Skoog-Ciecka-Krueger, Worklife Expectancy (Markov model 2012-17) | 40 | One per sex x initial state x education cohort, age-by-age. |
| `sck_yfs/` | Skoog-Ciecka-Krueger, Years to Final Separation (2012-17) | 40 | Same cohort structure as wle, includes YFS and WLE columns. |
| `nvsr_life_expectancy/` | NVSR Vol. 74 No. 12, U.S. State Life Tables 2022 | 3 | Table A (LE at birth), B (LE at 65), C (2021->2022 change), by state and sex. |
| `ecec/` | BLS Employer Costs for Employee Compensation, Dec 2025 | 7 | Table 1 by ownership (full component breakdown); Tables 2-7 by series. |
| `spf/` | Survey of Professional Forecasters, Q1 2026 (Philadelphia Fed) | 9 | Macro/price/yield medians, probability distributions, long-term forecasts. |
| `dvd/` | Expectancy Data, Dollar Value of a Day, 2023 valuation | 386 | 385 demographic time-use tables + Table 414 area-wage adjustment. |
| `dvd_valuation/` | DVD 2023 hourly valuation tables 386-412 | 27 | Per-activity SOC occupations, employment, mean wage, weight, weighted wage; index carries the hourly value with benefits. |

## Schemas

### sck_wle/wle_table_NN_*.csv
`age, wle_mean, wle_median, wle_mode, wle_sd, wle_skewness, wle_kurtosis,
wle_p10, wle_p25, wle_p75, wle_p90, wle_b_mean, wle_b_se`

### sck_yfs/yfs_table_NN_*.csv
`age, yfs_mean, yfs_median, yfs_mode, yfs_sd, yfs_skewness, yfs_kurtosis,
yfs_p10, yfs_p25, yfs_p75, yfs_p90, yfs_b_mean, yfs_b_se, wle_mean,
yfs_mean_minus_wle_mean, yfs_mean_div_wle_mean`

Cohorts (both): tables 1-10 Initially Active Men, 11-20 Initially Inactive Men,
21-30 Initially Active Women, 31-40 Initially Inactive Women; within each block
the 10 education levels run All, None-9th, 10-12 no diploma, GED, HS diploma,
Some college, Associate, Bachelor, Master, Professional/Doctoral.

### nvsr_life_expectancy/
Tables A and B: `area, total_rank, total_le_*, total_se, male_rank, male_le_*,
male_se, female_rank, female_le_*, female_se` (US row leaves rank/SE blank, not
applicable). Table C: `area, le_at_birth_2022, le_at_birth_2021,
change_2021_to_2022`.

### ecec/
Table 1: `compensation_component` + civilian/private/stategov cost and percent.
Tables 2-7: `series` + 8 benefit groups (total comp, wages, total benefits, paid
leave, supplemental pay, insurance, retirement & savings, legally required) each
as cost and percent.

### dvd/dvd_table_NNN.csv (demographic time-use tables 1-385)
`time_use_category, weekly_hours, hourly_value, dollar_value_of_a_day,
secondary_child_care, with_family, at_home, alone, participation_rate,
weekly_hrs_ci_lower, weekly_hrs_ci_upper`

33 category rows each (individual activities plus the Household Production,
Caring and Helping, Personal Time, Leisure, Work and Education subtotals, and
Total). The demographic for each table number is in `dvd/_index.csv`.

### dvd/dvd_table_414_area_wage_adjustment.csv
`state, area, adjustment_pct, is_state_total` (National-to-Area Wage Adjustment
Percentages, May 2023). 52 state/territory totals plus metro and nonmetro areas.

## Validation performed
- SCK wle/yfs: 40 tables each, zero age gaps; spot rows match the source; the
  wle age-18 means match the yfs WLE column (cross-source check).
- NVSR: 52 areas in each of Tables A, B, C; New Jersey, U.S., Florida values
  match the source exactly.
- ECEC: headline figures match (civilian $48.78, private $46.15, state/local
  $65.68).
- SPF: anchors match (GDP 2026 = 32,441; unemployment 4.5; 10-yr real GDP 2.10;
  10-yr bond 4.00).
- DVD: 385 tables, every table exactly 33 rows, table numbers 1-385 complete.
  The DVD identity (dollar value of a day = weekly hours x hourly value / 7) was
  checked on all 12,705 data rows; worst deviation 0.12 (rounding only),
  confirming column alignment throughout.

## Known limitations
- ECEC row labels come from the PDF text layer, which concatenates words without
  spaces (e.g., "Totalcompensation2"); the numbers and row order are exact. Row
  identity is unambiguous from position and `_index.csv`.
- DVD Table 414: about 8 metro rows whose names wrapped across lines retain an
  abbreviated label (e.g., a trailing state code); their adjustment percentages
  are correct.
- DVD valuation tables 386-412 are extracted to `dvd_valuation/`; their hourly
  value with benefits matches the `hourly_value` column in the demographic
  tables (cross-check). Tables 402 and 410 have no occupation list because those
  activities are valued at the person's own/median wage. The small Tables
  413/415-425 (descriptive/appendix) are not extracted.
- NVSR full age-by-age state life tables are not in this PDF; it carries only the
  summary tables. The complete tables live on the CDC FTP site the report cites.
