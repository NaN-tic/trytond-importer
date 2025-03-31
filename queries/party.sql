SELECT poblacion AS city,
    empresa AS company,
    p.nombre AS country,
    MAX(contacte) FILTER (WHERE contacte LIKE '%@%') AS email,
    nombre_comercial || '' || nombre_comercial2 as "name",
    telefonos as phone,
    direccion || '' || direccion2 as street,
    pr.nombre as subdivision,
    NULLIF(dni_nif, '.') as vat
FROM std.direcciones d
JOIN std.paises p on d.pais = p.pais
JOIN std.provincias pr on d.provincia = pr.provincia
GROUP BY city, company, country, "name", phone, street, subdivision, vat;