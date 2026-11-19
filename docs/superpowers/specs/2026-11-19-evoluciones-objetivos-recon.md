# Evoluciones y Objetivos: reconocimiento de la web app de EA (2026-11-19)

Solo lectura, con la sesión de Camilo, observando lo que la propia web app ya pide. No se llamó a
ningún método que reclame, compre, equipe o complete nada (`claim*`, `purchase*`, `addItemToSlot`…).

## Evoluciones (`services.Academy`)

- **Llamada**: `GET /ut/game/fc27/academy/hub/v2?offset=0&count=20&sortOrder=asc&slotStatus=STARTED`
  (la hace la app al abrir la sección Evoluciones; ~67 KB). Hay que atrapar la respuesta cruda
  con el hook de la extensión (`classifyUrl` debe reconocer `/academy/hub/v2`).
- **Respuesta** (claves de primer nivel): `categories[]`, `slots[]`, `activeSlotIds`,
  `inactiveSlotIds`, `activeTimedSlotIds`, `availableSlotsCount`, `activeSlotLimit`,
  `dynamicObjectivesUpdates`.
- `categories[]`: `{id, description, count, priority, slotIds[]}`. Hoy: 0 Evoluciones, 30 Campus,
  33 Recompensas, 29 Artículos cosméticos, 34 Roles++, 37 Laboratorio de Estilos de Juego+.
- `slots[]` (una evolución): `id`, `contentId`, `slotName`, `slotDescription`, `status`
  (`NOT_STARTED`…), `timed`, `endTime`, `endTimePurchaseVisibility`, `categoryId`,
  `isGkExclusive`, `isOutfieldExclusive`, `isMultiChoice`, `resetCount`, `totalRewardsCount`,
  `currencies[]` (coste), `academyTopRewards[]` (`{value=id de stat, count=mejora, maxValue}`),
  `elgReqs[]` (requisitos de elegibilidad: `{type, eligibilityKey, eligibilitySlot,
  eligibilityValue}`), `levels[]` (`{level, levelState, objectives[{objectiveId, name,
  description, multiplier, priority, isWeb, takeMeThereLink}], awards[], userSelectableAwards}`) y
  `randomPlayerPreview.academyBonusesPerLevel` (`{nivel: [{id de stat, totalBonus,
  initialAttributeValue?}]}`: la mejora acumulada por nivel sobre un jugador de ejemplo;
  `randomPlayerPreview.itemData` es un jugador de muestra, no hay que guardarlo).
- Al guardar: reducir cada slot a esos campos; no guardar `itemData` ni imágenes.

### Tablas de ids (del propio cliente de EA)

`AcademyStatEnum` (id de `academyTopRewards.value` y de `academyBonusesPerLevel.id`):

- Cara: 11 OVR, 12 PAC, 13 SHO, 14 PAS, 15 DRI, 16 DEF, 17 PHY.
- Portero (cara): 5 diving, 6 handling, 7 kicking, 8 reflexes, 9 speed, 10 positioning.
- Stats: 21 acceleration, 22 sprint_speed, 23 agility, 24 balance, 25 jumping, 26 stamina,
  27 strength, 28 reactions, 29 aggression, 30 composure, 31 interceptions, 32 positioning,
  33 vision, 34 ball_control, 35 crossing, 36 dribbling, 37 finishing, 38 fk_accuracy,
  39 heading, 40 long_passing, 41 short_passing, 42 def_awareness, 43 shot_power,
  44 long_shots, 45 standing_tackle, 46 sliding_tackle, 47 volleys, 48 curve, 49 penalties.
- Stats de portero: 50 diving, 51 handling, 52 kicking, 53 reflexes, 54 positioning.
- Posiciones: 61 CB, 62 RB, 63 RWB, 64 LB, 65 LWB, 66 CDM, 67 CM, 68 CAM, 69 LM, 70 RM,
  71 LW, 72 RW, 73 ST, 74 CF.
- 81 pie malo, 82 filigranas, 83 ritmo de ataque, 84 ritmo defensivo, 133 mejora cosmética.
- **Roles+ / Roles++** (151–202): 151 GK portero, 152 GK sweeper, 153–160 lateral derecho/izquierdo
  (fullback, falseback, wingback, offensive wingback), 161–163 y 198 central, 164–167 y 199
  pivote, 168–172 centrocampista, 173–180 banda (winger, wide midfielder, wide playmaker, inside
  forward), 181–184 mediapunta, 185–190 extremos, 191–194 delantero (advance forward, poacher,
  false 9, target forward), 195 GK ball-playing, 196–197 offensive falseback, 200–202 roles PLR.
- **PlayStyles** (301–336): 301 Finesse Shot, 302 Chip Shot, 303 Power Shot, 304 Dead Ball,
  305 Precision Header, 306 Acrobatic, 307 Low Driven Shot, 308 Gamechanger (trailblazing),
  309 Incisive Pass, 310 Pinged Pass, 311 Long Ball Pass, 312 Tiki Taka, 313 Whipped Pass,
  314 Inventive, 315 Jockey, 316 Block, 317 Intercept, 318 Anticipate, 319 Slide Tackle,
  320 Aerial Fortress, 321 Technical, 322 Rapid, 323 First Touch, 324 Trickster,
  325 Press Proven, 326 Quick Step, 327 Relentless, 328 Long Throw, 329 Bruiser, 330 Enforcer,
  331–336 portero (long thrower, footwork, cross claimer, 1v1 close down, far reach, deflector).
  (Nuestros ids de PlayStyle son los `eaId` de FUT.GG: 0–39; aquí son +301 con otro orden.)

`AcademyEligibilityAttribute` (id de `elgReqs.eligibilityKey`): 1 OVR, 2–7 cara (PAC, SHO, PAS,
DRI, DEF, PHY), 8–36 stats (8 acceleration, 9 sprint_speed, 10 agility, 11 balance, 12 jumping,
13 stamina, 14 strength, 15 reactions, 16 aggression, 17 composure, 18 interceptions,
19 positioning, 20 vision, 21 ball_control, 22 crossing, 23 dribbling, 24 finishing, 25 fk_acc,
26 heading, 27 long_passing, 28 short_passing, 29 def_awareness, 30 shot_power, 31 long_shots,
32 standing_tackle, 33 sliding_tackle, 34 volleys, 35 curve, 36 penalties), 37 pie malo,
38 filigranas, 39–40 ritmos, 41 definition_id, 42 nación, 43 club, 44 liga, 45 rareza,
46 rareza negada, 47 posición, 48 posición negada, 49 nº de posiciones, 50–52 nº de
PlayStyles (base, icono, total), 55 intransferible, 56–60 roles+/++, 62–63 grupo de rareza,
68–78 stats de portero, 79 fecha de nacimiento.
`AcademyEligibilityScope`: 0 MIN, 1 MAX, 2 EXACT, 3 BETWEEN.
`AcademyEligibilityType`: `PLAYER_ATTRIBUTE`, `SCOPE`, `ADDITIONAL_TARGET_VALUE`,
`ACADEMY_PLAYER_SLOTTING`. Un requisito va en varias filas (`elgReqs`) agrupadas por
`eligibilitySlot`; cómo se combinan (atributo + scope + valor) falta de decodificar con ejemplos.

Estados de slot: `NOT_STARTED, STARTED, ACTIVE, INACTIVE, COMPLETE, READY_FOR_REDEEM, EXPIRED,
CANCELED, LOCKED, DISABLED, ON_COOLDOWN, STRIPPED…`. Estados de nivel: `NOT_STARTED, IN_PROGRESS,
COMPLETED`.

## Objetivos (`services.Objectives`) — pendiente

`services.Objectives.objectivesRepository` guarda `activeCampaign` (temporada: título, xp, niveles,
premium, fechas), `categories` y `metaGroups` (se llenan al abrir la sección Objetivos; no se
visitó aún). Métodos de lectura: `requestCategories`, `requestCategoryById`, `requestGroup`.
Todo lo que reclama (`claimLevelReward`, `claimMetaUTRewards`, `claimExpiredRewards`) o compra
(`purchasePremiumPass`) queda **fuera**. Falta capturar la respuesta cruda al abrir Objetivos.

## Plan (por hacer, en orden)

1. Extensión: reconocer `/academy/hub/v2` y enviar una versión reducida (sin `itemData`) a
   `POST /import/evolutions` (con tests de `parse`/`hook`/`background`).
2. API: tabla `evolutions` (+ categorías), `POST /import/evolutions` (token) y `GET /evolutions`
   (filtros por categoría/estado; mejoras con nombres de stat).
3. Web: página `/evoluciones` (hoy placeholder) con tarjetas: nombre, descripción, categoría,
   caducidad, mejoras por nivel, objetivos, coste y requisitos decodificados.
4. Después, igual para Objetivos y para la Galería.
5. Ideas de valor: qué evolución conviene para cada carta de tu club (cruzar requisitos con tu
   club y las mejoras con el meta rating).
