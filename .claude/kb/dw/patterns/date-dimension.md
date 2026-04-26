# Date Dimension Generator

> **Purpose**: Generate a complete dim_date calendar table in BigQuery with all standard flags
> **MCP Validated**: 2026-04-24

## When to Use

- Bootstrapping a new dimensional warehouse that needs a calendar dimension
- Adding calendar attributes (quarter, week, is_weekend, is_holiday) to support BI filtering
- Generating the date spine before loading any fact tables

## Implementation

```sql
-- ============================================================
-- dim_date generator: creates one row per calendar day
-- Range: 2020-01-01 to 2030-12-31 (adjust as needed)
-- Holiday table: project.dw.dim_holiday_calendar (optional)
-- ============================================================

CREATE OR REPLACE TABLE `project.dw.dim_date`
OPTIONS (
    description = 'Calendar dimension. grain: one row per calendar day. Range: 2020-2030.'
)
AS

WITH date_spine AS (
    -- Generate one row per day using GENERATE_DATE_ARRAY
    SELECT d AS full_date
    FROM UNNEST(
        GENERATE_DATE_ARRAY('2020-01-01', '2030-12-31', INTERVAL 1 DAY)
    ) AS d
),

calendar AS (
    SELECT
        full_date,

        -- Integer surrogate key: YYYYMMDD
        CAST(FORMAT_DATE('%Y%m%d', full_date) AS INT64)     AS date_key,

        -- Year / Quarter / Month
        EXTRACT(YEAR    FROM full_date)                     AS calendar_year,
        EXTRACT(QUARTER FROM full_date)                     AS calendar_quarter,
        EXTRACT(MONTH   FROM full_date)                     AS month_number,
        FORMAT_DATE('%B', full_date)                        AS month_name,
        FORMAT_DATE('%b', full_date)                        AS month_abbrev,

        -- Week / Day
        EXTRACT(ISOWEEK FROM full_date)                     AS week_of_year,
        EXTRACT(ISOYEAR FROM full_date)                     AS iso_year,
        EXTRACT(DAYOFWEEK FROM full_date)                   AS day_of_week_sunday,  -- 1=Sun
        MOD(EXTRACT(DAYOFWEEK FROM full_date) + 5, 7) + 1  AS day_of_week_monday,  -- 1=Mon
        FORMAT_DATE('%A', full_date)                        AS day_name,
        FORMAT_DATE('%a', full_date)                        AS day_abbrev,
        EXTRACT(DAY FROM full_date)                         AS day_of_month,
        EXTRACT(DAYOFYEAR FROM full_date)                   AS day_of_year,

        -- Weekend flag (Saturday=7, Sunday=1 in DAYOFWEEK)
        EXTRACT(DAYOFWEEK FROM full_date) IN (1, 7)         AS is_weekend,

        -- First/last day flags
        full_date = DATE_TRUNC(full_date, MONTH)            AS is_first_day_of_month,
        full_date = LAST_DAY(full_date, MONTH)              AS is_last_day_of_month,
        full_date = DATE_TRUNC(full_date, QUARTER)          AS is_first_day_of_quarter,
        full_date = LAST_DAY(full_date, QUARTER)            AS is_last_day_of_quarter,
        full_date = DATE_TRUNC(full_date, YEAR)             AS is_first_day_of_year,
        full_date = LAST_DAY(full_date, YEAR)               AS is_last_day_of_year,

        -- Fiscal calendar (adjust offset to match company fiscal year)
        -- Assumes fiscal year starts October 1 (offset = -9 months)
        EXTRACT(YEAR FROM DATE_ADD(full_date, INTERVAL 3 MONTH))   AS fiscal_year,
        EXTRACT(QUARTER FROM DATE_ADD(full_date, INTERVAL 3 MONTH)) AS fiscal_quarter,

        -- Relative date helpers (recalculated at query time via view, or stored)
        DATE_DIFF(CURRENT_DATE(), full_date, DAY)           AS days_ago,

        -- Placeholder: holiday flag populated from join below
        FALSE AS is_holiday,
        CAST(NULL AS STRING) AS holiday_name

    FROM date_spine
)

-- Optional: join to a static holiday calendar table
-- If you maintain dim_holiday_calendar, replace the SELECT above with:
--
-- SELECT
--     c.*,
--     COALESCE(h.is_holiday, FALSE) AS is_holiday,
--     h.holiday_name
-- FROM calendar c
-- LEFT JOIN `project.dw.dim_holiday_calendar` h
--     ON c.full_date = h.holiday_date

SELECT * FROM calendar;
```

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Date range | 2020-01-01 to 2030-12-31 | Extend as needed; cheap to regenerate |
| Fiscal offset | +3 months | Adjust for company fiscal year start |
| Holiday table | Optional join | Populate `is_holiday` from external calendar |
| Surrogate key | `YYYYMMDD` integer | Readable, sortable, no sequence required |

## Example Usage

```sql
-- Rolling 13-month revenue trend with fiscal quarter label
SELECT
    d.fiscal_year,
    d.fiscal_quarter,
    d.month_name,
    SUM(ol.net_amount) AS monthly_revenue
FROM `project.dw.fct_order_lines` ol
JOIN `project.dw.dim_date` d ON ol.order_date_key = d.date_key
WHERE d.full_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 13 MONTH)
GROUP BY 1, 2, 3
ORDER BY MIN(d.full_date);

-- Weekend vs weekday order split
SELECT
    d.is_weekend,
    COUNT(*)            AS order_lines,
    SUM(ol.net_amount)  AS revenue
FROM `project.dw.fct_order_lines` ol
JOIN `project.dw.dim_date` d ON ol.order_date_key = d.date_key
GROUP BY 1;
```

## See Also

- [patterns/star-schema-design.md](star-schema-design.md)
- [concepts/fact-tables.md](../concepts/fact-tables.md)
- [concepts/dimensional-modeling.md](../concepts/dimensional-modeling.md)
