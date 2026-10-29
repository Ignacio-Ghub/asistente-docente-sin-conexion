import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # Vercel no añade esta carpeta

from http.server import BaseHTTPRequestHandler

from _asistente import CODIGO, responder

# Registro de la prueba: el perfil que guarda el docente (nunca datos de sus estudiantes) va a la base
# de Notion «Docentes registrados en Tiza» por el mismo flujo de n8n que las opiniones.
N8N = "https://n8n.jibalab.com/webhook/jiba-opinion-asistente-v1"
SECRETO = os.environ.get("OPINION_SECRETO", "")


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not CODIGO or self.headers.get("X-Codigo", "").strip().lower() != CODIGO.lower():
            return responder(self, {"ok": False, "error": "Contraseña incorrecta."}, 401)
        try:
            largo = min(int(self.headers.get("Content-Length", 0)), 20_000)
            d = json.loads(self.rfile.read(largo) or b"{}")
        except ValueError:
            return responder(self, {"ok": False}, 400)
        datos = {"tipo": "Perfil", "id": str(d.get("id", ""))[:40], "nombre": str(d.get("nombre", ""))[:120],
                 "escuela": str(d.get("escuela", ""))[:200], "estado": str(d.get("estado", ""))[:40].replace(",", ""),
                 "municipio": str(d.get("municipio", ""))[:80], "nivel": str(d.get("nivel", ""))[:40].replace(",", ""),
                 "grados": str(d.get("grados", ""))[:200], "areas": [str(x).replace(",", "")[:60] for x in d.get("areas", [])][:10],
                 "multigrado": "Sí" if d.get("multigrado") else "No"}
        pedido = urllib.request.Request(N8N, data=json.dumps({"s": SECRETO, "r": datos}).encode(),
                                        headers={"Content-Type": "application/json", "User-Agent": "curl/8.7.1"}, method="POST")
        try:
            with urllib.request.urlopen(pedido, timeout=30) as r:
                ok = json.loads(r.read() or b"{}").get("object") == "page"
        except Exception:
            ok = False
        responder(self, {"ok": ok}, 200 if ok else 502)
