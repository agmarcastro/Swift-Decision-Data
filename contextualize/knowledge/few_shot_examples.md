# Few-Shot SQL Examples — InfoAgent

These examples ground the SQL Agent with verified query patterns for the InfoAgent Star Schema.
Each entry maps an executive question to a correct PostgreSQL query.

---

## Type 1 — Pure SQL Examples

### Q: What were the sales figures for yesterday?

```sql
SELECT
    SUM(fv.valor_total)   AS total_revenue,
    SUM(fv.quantidade)    AS total_units,
    COUNT(fv.id_venda)    AS total_transactions
FROM fato_vendas fv
JOIN dim_tempo dt ON fv.id_tempo = dt.id_tempo
WHERE dt.data = CURRENT_DATE - 1;
```

---

### Q: What is the total capital tied up in inventory for the TV/Audio department?

```sql
SELECT
    dp.departamento,
    SUM(fe.qtd_disponivel + fe.qtd_transito) AS total_units_in_stock
FROM fato_estoque fe
JOIN dim_produto dp ON fe.id_produto = dp.id_produto
WHERE dp.departamento = 'TV/Audio'
GROUP BY dp.departamento;
```

---

### Q: Which 5 stores had the lowest Notebook sales this quarter, and who are their managers?

```sql
SELECT
    dl.nome_loja,
    dl.gerente,
    SUM(fv.valor_total) AS total_sales
FROM fato_vendas fv
JOIN dim_loja dl ON fv.id_loja = dl.id_loja
JOIN dim_produto dp ON fv.id_produto = dp.id_produto
JOIN dim_tempo dt ON fv.id_tempo = dt.id_tempo
WHERE dp.categoria ILIKE '%notebook%'
  AND dt.data >= date_trunc('quarter', CURRENT_DATE)
GROUP BY dl.id_loja, dl.nome_loja, dl.gerente
ORDER BY total_sales ASC
LIMIT 5;
```

---

### Q: Did the flagship store outperform the average of other branches during the last holiday?

```sql
WITH last_holiday AS (
    SELECT MAX(data) AS holiday_date
    FROM dim_tempo
    WHERE flg_feriado = true AND data < CURRENT_DATE
),
holiday_sales AS (
    SELECT
        dl.nome_loja,
        dl.id_loja,
        SUM(fv.valor_total) AS sales
    FROM fato_vendas fv
    JOIN dim_loja dl ON fv.id_loja = dl.id_loja
    JOIN dim_tempo dt ON fv.id_tempo = dt.id_tempo
    CROSS JOIN last_holiday lh
    WHERE dt.data = lh.holiday_date
    GROUP BY dl.id_loja, dl.nome_loja
)
SELECT
    nome_loja,
    sales,
    AVG(sales) OVER () AS avg_all_stores,
    sales - AVG(sales) OVER () AS variance_from_avg
FROM holiday_sales
ORDER BY sales DESC;
```

---

### Q: Is there a stockout risk for PlayStation 5 at mall locations heading into this weekend?

```sql
SELECT
    dl.nome_loja,
    dp.nome_produto,
    fe.qtd_disponivel,
    fe.qtd_transito,
    CASE WHEN fe.qtd_disponivel < 5 THEN 'STOCKOUT RISK' ELSE 'OK' END AS status
FROM fato_estoque fe
JOIN dim_produto dp ON fe.id_produto = dp.id_produto
JOIN dim_loja dl ON fe.id_loja = dl.id_loja
WHERE dp.nome_produto ILIKE '%playstation 5%'
  AND dl.nome_loja ILIKE '%mall%'
  AND fe.data_posicao = (
      SELECT MAX(data_posicao) FROM fato_estoque
  )
ORDER BY fe.qtd_disponivel ASC;
```

---

### Q: Among customers who purchased Premium Smartphones this month, how many also included Bluetooth headphones or phone cases in the same transaction?

```sql
WITH smartphone_buyers AS (
    SELECT DISTINCT fv.id_venda, fv.id_cliente
    FROM fato_vendas fv
    JOIN dim_produto dp ON fv.id_produto = dp.id_produto
    JOIN dim_tempo dt ON fv.id_tempo = dt.id_tempo
    WHERE dp.categoria ILIKE '%smartphone%'
      AND dp.nome_produto ILIKE '%premium%'
      AND dt.data >= date_trunc('month', CURRENT_DATE)
),
with_accessories AS (
    SELECT DISTINCT sb.id_venda
    FROM smartphone_buyers sb
    JOIN fato_vendas fv2 ON sb.id_venda = fv2.id_venda
    JOIN dim_produto dp2 ON fv2.id_produto = dp2.id_produto
    WHERE dp2.categoria ILIKE '%headphone%'
       OR dp2.categoria ILIKE '%case%'
       OR dp2.nome_produto ILIKE '%bluetooth%'
)
SELECT
    COUNT(DISTINCT sb.id_venda)  AS total_smartphone_transactions,
    COUNT(DISTINCT wa.id_venda)  AS transactions_with_accessories,
    ROUND(
        COUNT(DISTINCT wa.id_venda)::numeric / NULLIF(COUNT(DISTINCT sb.id_venda), 0) * 100, 1
    ) AS attachment_rate_pct
FROM smartphone_buyers sb
LEFT JOIN with_accessories wa ON sb.id_venda = wa.id_venda;
```

---

## Type 2 — KPI-Grounded SQL Examples

### Q: What was the gross profit margin for the Smartphone category over the past week vs the preceding week?

*(KPI: Gross Profit Margin — formula: (SUM(valor_total) - SUM(custo_total)) / SUM(valor_total))*

```sql
SELECT
    CASE
        WHEN dt.data >= date_trunc('week', CURRENT_DATE)
        THEN 'Current Week'
        ELSE 'Previous Week'
    END AS period,
    SUM(fv.valor_total)  AS total_revenue,
    SUM(fv.custo_total)  AS total_cogs,
    ROUND(
        (SUM(fv.valor_total) - SUM(fv.custo_total)) / NULLIF(SUM(fv.valor_total), 0) * 100, 2
    ) AS gross_profit_margin_pct
FROM fato_vendas fv
JOIN dim_produto dp ON fv.id_produto = dp.id_produto
JOIN dim_tempo dt ON fv.id_tempo = dt.id_tempo
WHERE dp.categoria ILIKE '%smartphone%'
  AND dt.data >= date_trunc('week', CURRENT_DATE) - INTERVAL '7 days'
GROUP BY period
ORDER BY period DESC;
```

---

### Q: What is our attachment rate (cross-sell rate) within the Mobile category?

*(KPI: Attachment Rate — see few_shot_examples.md for formula)*

```sql
WITH mobile_transactions AS (
    SELECT DISTINCT fv.id_venda
    FROM fato_vendas fv
    JOIN dim_produto dp ON fv.id_produto = dp.id_produto
    WHERE dp.departamento = 'Telephony'
),
with_accessories AS (
    SELECT DISTINCT mt.id_venda
    FROM mobile_transactions mt
    JOIN fato_vendas fv2 ON mt.id_venda = fv2.id_venda
    JOIN dim_produto dp2 ON fv2.id_produto = dp2.id_produto
    WHERE dp2.departamento != 'Telephony'
)
SELECT
    COUNT(DISTINCT mt.id_venda)  AS total_mobile_transactions,
    COUNT(DISTINCT wa.id_venda)  AS transactions_with_cross_sell,
    ROUND(
        COUNT(DISTINCT wa.id_venda)::numeric / NULLIF(COUNT(DISTINCT mt.id_venda), 0) * 100, 1
    ) AS attachment_rate_pct
FROM mobile_transactions mt
LEFT JOIN with_accessories wa ON mt.id_venda = wa.id_venda;
```

---

### Q: What is our loyalty program contribution this month?

*(KPI: Loyalty Program Contribution — formula: revenue from loyalty members / total revenue)*

```sql
SELECT
    ROUND(
        SUM(CASE WHEN dc.categoria_clube_info IN ('Bronze','Silver','Gold')
            THEN fv.valor_total ELSE 0 END)
        / NULLIF(SUM(fv.valor_total), 0) * 100, 2
    ) AS loyalty_contribution_pct,
    SUM(CASE WHEN dc.categoria_clube_info = 'Gold'   THEN fv.valor_total ELSE 0 END) AS gold_revenue,
    SUM(CASE WHEN dc.categoria_clube_info = 'Silver' THEN fv.valor_total ELSE 0 END) AS silver_revenue,
    SUM(CASE WHEN dc.categoria_clube_info = 'Bronze' THEN fv.valor_total ELSE 0 END) AS bronze_revenue,
    SUM(fv.valor_total) AS total_revenue
FROM fato_vendas fv
JOIN dim_cliente dc ON fv.id_cliente = dc.id_cliente
JOIN dim_tempo dt ON fv.id_tempo = dt.id_tempo
WHERE dt.data >= date_trunc('month', CURRENT_DATE);
```

---

## Type 3 — Hybrid Examples

### Q: Does inventory turnover at mall locations justify the showroom space they occupy?

*(SQL part — DSI calculation; RAG part — business judgment on DSI threshold)*

```sql
WITH mall_sales AS (
    SELECT
        dl.id_loja,
        dl.nome_loja,
        SUM(fv.custo_total)      AS total_cogs,
        COUNT(DISTINCT dt.data)  AS selling_days
    FROM fato_vendas fv
    JOIN dim_loja dl ON fv.id_loja = dl.id_loja
    JOIN dim_tempo dt ON fv.id_tempo = dt.id_tempo
    WHERE dl.nome_loja ILIKE '%mall%'
    GROUP BY dl.id_loja, dl.nome_loja
),
mall_inventory AS (
    SELECT
        dl.id_loja,
        AVG(fe.qtd_disponivel) AS avg_inventory
    FROM fato_estoque fe
    JOIN dim_loja dl ON fe.id_loja = dl.id_loja
    WHERE dl.nome_loja ILIKE '%mall%'
    GROUP BY dl.id_loja
)
SELECT
    ms.nome_loja,
    ms.total_cogs,
    mi.avg_inventory,
    ROUND(mi.avg_inventory / NULLIF(ms.total_cogs, 0) * 365, 1) AS dsi_days
FROM mall_sales ms
JOIN mall_inventory mi ON ms.id_loja = mi.id_loja
ORDER BY dsi_days DESC;
```
