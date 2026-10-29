import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # Vercel no añade esta carpeta

from _asistente import Base, generar


class handler(Base):
    def accion(self, d):
        return generar("plan", d)
