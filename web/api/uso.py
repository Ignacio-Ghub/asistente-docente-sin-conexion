import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # Vercel no añade esta carpeta

from http.server import BaseHTTPRequestHandler

from _asistente import CODIGO, responder

# Contador anónimo de uso: qué función se usó y cuándo. Nunca nombres, temas ni calificaciones.
N8N = "https://n8n.jibalab.com/webhook/jiba-opinion-asistente-v1"
SECRETO = os.environ.get("OPINION_SECRETO", "")
EVENTOS = {"Abrió Tiza", "Plan generado", "Evaluación generada", "Repaso generado", "Guía sin conexión",
           "Guardó un borrador", "Anotó calificaciones"}


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not CODIGO or self.headers.get("X-Codigo", "").strip().lower() != CODIGO.lower():
            return responder(self, {"ok": False}, 401)
        try:
            d = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 20_000)) or b"{}")
        except ValueError:
            return responder(self, {"ok": False}, 400)
        id_ = str(d.get("id", ""))
        if not re.fullmatch(r"[a-z0-9-]{8,40}", id_):
            return responder(self, {"ok": False}, 400)
        enviados = 0
        for e in d.get("eventos", [])[:5]:
            evento, momento = str(e.get("evento", "")), str(e.get("t", ""))
            if evento in EVENTOS and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?Z", momento):
                datos = {"tipo": "Uso", "evento": evento, "momento": momento, "id": id_}
                pedido = urllib.request.Request(N8N, data=json.dumps({"s": SECRETO, "r": datos}).encode(),
                                                headers={"Content-Type": "application/json", "User-Agent": "curl/8.7.1"}, method="POST")
                try:
                    with urllib.request.urlopen(pedido, timeout=30) as r:
                        if json.loads(r.read() or b"{}").get("object") != "page":
                            break
                except Exception:
                    break
            enviados += 1  # un evento no válido se descarta para que no bloquee la cola
        responder(self, {"ok": True, "enviados": enviados})
