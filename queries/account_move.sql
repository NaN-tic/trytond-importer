SELECT
    MAX(a.subcta) FILTER (WHERE a.empresa = 1 OR a.empresa = 2) AS account_code,
    MAX(s.titulo) FILTER (WHERE a.empresa = 1) AS account_name,
    MAX(importe_haber) FILTER (WHERE tipo = 'H') AS credit,
    MAX(importe_debe) FILTER (WHERE tipo = 'D') AS debit,
    descripcion_1 || '-' || descripcion_2 AS "description",
    fecha_entrada AS post_date,
    fecha_contable AS "date",
    asiento AS "number",
    a.moneda AS currency
FROM std.apuntes a
JOIN std.subcuentas s on a.subcta = s.subcta
GROUP BY "description", post_date, "date", "number", currency;
