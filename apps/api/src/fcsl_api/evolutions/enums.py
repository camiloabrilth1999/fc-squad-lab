"""Nombres de los ids de EA para Evoluciones (`AcademyStatEnum` del cliente de la web app).

Ver `docs/superpowers/specs/2026-11-19-evoluciones-objetivos-recon.md`. Los nombres de
stat están en español como en el juego; los PlayStyles y los roles conservan su nombre.
"""

_STATS: dict[int, str] = {
    # cara
    11: "Valoración general",
    12: "Ritmo",
    13: "Tiro",
    14: "Pase",
    15: "Regate",
    16: "Defensa",
    17: "Físico",
    # portero (cara)
    5: "Estirada",
    6: "Parada",
    7: "Saque",
    8: "Reflejos",
    9: "Velocidad (portero)",
    10: "Colocación (portero)",
    # stats
    21: "Aceleración",
    22: "Velocidad",
    23: "Agilidad",
    24: "Equilibrio",
    25: "Salto",
    26: "Resistencia",
    27: "Fuerza",
    28: "Reacciones",
    29: "Agresividad",
    30: "Sangre fría",
    31: "Interceptaciones",
    32: "Pos. ataque",
    33: "Visión",
    34: "Control",
    35: "Centros",
    36: "Regate (stat)",
    37: "Definición",
    38: "Precisión de tiros libres",
    39: "Cabezazo",
    40: "Pase largo",
    41: "Pase corto",
    42: "Anticipación",
    43: "Potencia de tiro",
    44: "Tiro lejano",
    45: "Entrada de pie",
    46: "Entrada en plancha",
    47: "Voleas",
    48: "Efecto",
    49: "Penaltis",
    50: "Estirada (stat)",
    51: "Parada (stat)",
    52: "Saque (stat)",
    53: "Reflejos (stat)",
    54: "Colocación (stat)",
    81: "Pie malo",
    82: "Filigranas",
    83: "Ritmo de ataque",
    84: "Ritmo defensivo",
    133: "Mejora cosmética",
}

_POSITIONS = {
    61: "DFC", 62: "LD", 63: "CAD", 64: "LI", 65: "CAI", 66: "MCD", 67: "MC", 68: "MCO",
    69: "MI", 70: "MD", 71: "EI", 72: "ED", 73: "DC", 74: "SD",
}  # fmt: skip

_PLAYSTYLES = {
    301: "Finesse Shot", 302: "Chip Shot", 303: "Power Shot", 304: "Dead Ball",
    305: "Precision Header", 306: "Acrobatic", 307: "Low Driven Shot", 308: "Gamechanger",
    309: "Incisive Pass", 310: "Pinged Pass", 311: "Long Ball Pass", 312: "Tiki Taka",
    313: "Whipped Pass", 314: "Inventive", 315: "Jockey", 316: "Block", 317: "Intercept",
    318: "Anticipate", 319: "Slide Tackle", 320: "Aerial Fortress", 321: "Technical",
    322: "Rapid", 323: "First Touch", 324: "Trickster", 325: "Press Proven",
    326: "Quick Step", 327: "Relentless", 328: "Long Throw", 329: "Bruiser", 330: "Enforcer",
    331: "Long Throw (portero)", 332: "Footwork", 333: "Cross Claimer", 334: "1v1 Close Down",
    335: "Far Reach", 336: "Deflector",
}  # fmt: skip

_ROLES = {
    151: "Portero", 152: "Líbero", 153: "Lateral derecho (carrilero)", 154: "Lateral derecho (falso)",
    155: "Carrilero derecho", 156: "Carrilero derecho ofensivo", 157: "Lateral izquierdo (carrilero)",
    158: "Lateral izquierdo (falso)", 159: "Carrilero izquierdo", 160: "Carrilero izquierdo ofensivo",
    161: "Central (defensor)", 162: "Central (stopper)", 163: "Central (con balón)",
    164: "Pivote (posicional)", 165: "Pivote (central)", 166: "Pivote (organizador)",
    167: "Pivote (abierto)", 168: "Centrocampista (llegador)", 169: "Centrocampista (posicional)",
    170: "Centrocampista (organizador)", 171: "Centrocampista (creador)",
    172: "Centrocampista (interior)", 173: "Mediocampista derecho (extremo)",
    174: "Mediocampista derecho (abierto)", 175: "Mediocampista derecho (creador)",
    176: "Mediocampista derecho (delantero interior)", 177: "Mediocampista izquierdo (extremo)",
    178: "Mediocampista izquierdo (abierto)", 179: "Mediocampista izquierdo (creador)",
    180: "Mediocampista izquierdo (delantero interior)", 181: "Mediapunta (creador)",
    182: "Mediapunta (sombra)", 183: "Mediapunta (interior)", 184: "Mediapunta (clásico 10)",
    185: "Extremo derecho", 186: "Extremo derecho (delantero interior)",
    187: "Extremo derecho (creador)", 188: "Extremo izquierdo",
    189: "Extremo izquierdo (delantero interior)", 190: "Extremo izquierdo (creador)",
    191: "Delantero (avanzado)", 192: "Delantero (cazagoles)", 193: "Falso 9",
    194: "Delantero (referencia)", 195: "Portero (con balón)", 196: "Lateral derecho (falso ofensivo)",
    197: "Lateral izquierdo (falso ofensivo)", 198: "Central (lateral)", 199: "Pivote (llegador)",
}  # fmt: skip


def stat_name(stat_id: int) -> str:
    """Nombre legible de un id de mejora; los roles llevan el prefijo «Rol»."""
    if stat_id in _STATS:
        return _STATS[stat_id]
    if stat_id in _POSITIONS:
        return f"Posición {_POSITIONS[stat_id]}"
    if stat_id in _PLAYSTYLES:
        return _PLAYSTYLES[stat_id]
    if stat_id in _ROLES:
        return f"Rol {_ROLES[stat_id]}"
    return f"Stat {stat_id}"
