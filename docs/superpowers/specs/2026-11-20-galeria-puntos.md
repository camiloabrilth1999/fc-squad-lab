# Galería: puntos por carta (calibración con soluciones de EasySBC)

Estado a 2026-11-20. `apps/api/src/fcsl_api/gallery/points.py` implementa
`puntos = base(media) × factor(rareza)`. EasySBC solo se usó para observar valores (guía de
desarrollo): no es una dependencia en ejecución.

## Cómo se observó
Cada set de la Galería de EasySBC guarda una solución ya calculada; abrirla no gasta cupo diario.
Cada carta muestra su media, sus puntos y su precio. Se leyó el DOM de ~35 soluciones (≈270 cartas
distintas) y se cruzaron los ids (`players/<id>.png`) con nuestra tabla `cards`.

## Base por media (cartas normales, factor 1)
≤64 → 20 · 65‑74 → 35 · 75 → 90 · 76 → 100 · 77 → 120 · 78 → 140 · 79 → 160 · 80 → 180 ·
81 → 280 · 82 → 340 · 83 → 410 · 84 → 830 · 85 → 2.100 · 86 → 4.100 · 87 → 5.500 · 88 → 8.300 ·
89 → 11.000 · 90 → 14.000 · 91 → 19.000 · 92 → 20.000 · 93 → 25.000. De 94 en adelante: estimado.
(232 de 270 cartas observadas coinciden exactamente con la base de su media.)

## Factor por rareza
Observado: 1 (común/rara, FC Heritage, Squad Foundations) · 1,25 (TOTW, Destined for Glory, POTM
Liga F, RTTK de la Champions) · 1,5 (Future Stars, Ultimate Scream, Hall of FUT: Unleashed) ·
2,25 (Icono base). Una carta evolucionada puntúa con su media nueva ×1,875.

## Lo que NO es solo rareza
- **Héroes base**: de 8 cartas observadas, 5 dan ×1,25 y 3 (Ljungberg, Aimar, Kluivert) ×1,875 con
  la misma rareza y media. No son del club del usuario, así que no es *First Owner*. Se deja
  ×1,25 marcado como estimado (`exact=False`).
- **Cartas que EasySBC cuenta y FUT.GG no lista** (≈950 de 21.479): ×1,875 y ×2,25 (probablemente
  las rarezas más nuevas: Season 1, Hall of FUT, etc.). Están fuera de nuestra tabla `cards`, así
  que el solver no las elige.

## Sin observar
Star Performer, Debut International Icon, Ultimate Scream Hero, RTTK de Europa League /
Conference / Women's CL, Showdown, POTM de cada liga salvo Liga F. Usan el factor por defecto de
las cartas especiales (1,25; 2,25 si son Iconos) y se muestran con «~».
