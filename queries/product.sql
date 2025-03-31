SELECT
    MAX(m2.subcta) FILTER (WHERE m2.tipo_subcta = 'C') AS account_expense,
    MAX(m2.subcta) FILTER (WHERE m2.tipo_subcta = 'V') AS account_revenue,
    m.empresa as company,
    p.precio as cost_price,
    'fixed' as cost_price_method,
    m.descripcion as "description",
    m.descripcion as "name",
    p.codigo as code
FROM std.m0302 m
JOIN std.m0313 m2 ON m.codigo = m2.codigo
JOIN std.m0308 p ON p.codigo = m2.codigo
GROUP BY m.empresa, p.precio, m.descripcion, p.codigo;