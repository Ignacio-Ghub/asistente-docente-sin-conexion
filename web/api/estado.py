import os
from http.server import BaseHTTPRequestHandler

from _asistente import SIMULAR, responder


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        listo = SIMULAR or bool(os.environ.get("ANTHROPIC_API_KEY"))
        responder(self, {"ok": listo, "simulado": SIMULAR})
