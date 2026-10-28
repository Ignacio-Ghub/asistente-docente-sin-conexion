"""Prepara el currículo oficial para usarlo sin conexión en el teléfono.

Lee api/curriculo/*.json (texto extraído de los documentos del MPPE) y escribe en
public/curriculo/ una versión ordenada por bloques: [{"bloque": ..., "items": [...]}].
Uso: python3 preparar_curriculo_offline.py
"""
import glob
import json
import os
import re

VIÑETAS = ("\uf0b7", "\uf02d", "•", "■", "§")  # viñetas que usan los PDF del MPPE


def oracion(t):
    """Algunos documentos vienen en MAYÚSCULAS; se pasan a oración para leerlos mejor en el teléfono."""
    if t.isupper():
        t = t.capitalize()
        for nombre in ("Venezuela", "Caracas", "Simón Bolívar", "Bolívar", "Tierra", "Caribe"):
            t = re.sub(r"\b" + nombre.lower() + r"\b", nombre, t)
    return t


def bloques(texto):
    salida, actual, item = [], None, ""

    def cerrar_item():
        nonlocal item
        if item.strip() and actual is not None:
            actual["items"].append(oracion(re.sub(r"\s+", " ", item).strip()))
        item = ""

    for linea in texto.splitlines():
        l = linea.strip()
        if not l or re.match(r"^(PRIMER|SEGUNDO|TERCER|CUARTO|QUINTO|SEXTO)\s+(GRADO|AÑO)$", l) \
                or l.startswith("CONTENIDOS"):
            continue
        if l.startswith(VIÑETAS):
            cerrar_item()
            if actual is None:
                actual = {"bloque": "Contenidos", "items": []}
                salida.append(actual)
            item = l.lstrip("".join(VIÑETAS) + " ").strip()
        elif item and (l[0].islower() or not item.rstrip().endswith((".", ":"))):
            item += " " + l  # continuación de la viñeta anterior
        else:
            cerrar_item()
            actual = {"bloque": oracion(l), "items": []}
            salida.append(actual)
    cerrar_item()
    return [b for b in salida if b["items"]]


os.makedirs("public/curriculo", exist_ok=True)
for f in sorted(glob.glob("api/curriculo/*.json")):
    d = json.load(open(f))
    out = {"fuentes": d.get("fuentes", {}), "areas": {a: bloques(t) for a, t in d["areas"].items()}}
    json.dump(out, open("public/curriculo/" + os.path.basename(f), "w"), ensure_ascii=False, separators=(",", ":"))
    print(os.path.basename(f), {a: sum(len(b["items"]) for b in v) for a, v in out["areas"].items()})
