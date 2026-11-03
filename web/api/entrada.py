import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # Vercel no añade esta carpeta

from http.server import BaseHTTPRequestHandler

from _asistente import CODIGO, responder

# Enlace personal de quien pidió probar Tiza en la encuesta: marca en su fila de Notion que pudo entrar.
N8N = "https://n8n.jibalab.com/webhook/jiba-tiza-entrada-910bd4"
SECRETO = os.environ.get("OPINION_SECRETO", "")


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not CODIGO or self.headers.get("X-Codigo", "").strip().lower() != CODIGO.lower():
            return responder(self, {"ok": False}, 401)
        try:
            d = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 2_000)) or b"{}")
        except ValueError:
            return responder(self, {"ok": False}, 400)
        datos = {"s": SECRETO, "p": str(d.get("p", ""))[:40], "c": str(d.get("c", ""))[:2]}
        pedido = urllib.request.Request(N8N, data=json.dumps(datos).encode(),
                                        headers={"Content-Type": "application/json", "User-Agent": "curl/8.7.1"}, method="POST")
        try:
            with urllib.request.urlopen(pedido, timeout=30) as r:
                ok = json.loads(r.read() or b"{}").get("ok") is True
        except Exception:
            ok = False
        responder(self, {"ok": ok}, 200 if ok else 502)
