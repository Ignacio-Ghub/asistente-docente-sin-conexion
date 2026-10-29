import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # Vercel no añade esta carpeta

from _asistente import Base, es_educacion_fisica, generar, revisar_clave


class handler(Base):
    def accion(self, d):
        r = generar("evaluacion", d)
        # Una lista de observación no tiene clave de respuestas que revisar.
        r["revision"] = "no_aplica" if es_educacion_fisica(d.get("area", "")) else revisar_clave(r["texto"])
        return r
