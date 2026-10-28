import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # Vercel no añade esta carpeta

from http.server import BaseHTTPRequestHandler

from _asistente import CODIGO, responder

# La opinión es anónima: solo se reenvían las respuestas, sin datos de quien opina.
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
        # Dos tipos: la opinión del botón «Dar mi opinión» y la valoración rápida de un borrador.
        datos = {"tipo": "Valoración rápida" if d.get("tipo") == "Valoración rápida" else "Opinión",
                 "probo": [str(x) for x in d.get("probo", [])][:4], "util": str(d.get("util", ""))[:20],
                 "usaria": str(d.get("usaria", ""))[:20], "mejoras": str(d.get("mejoras", ""))[:1900],
                 "valoracion": str(d.get("valoracion", ""))[:20], "borrador": str(d.get("borrador", ""))[:40],
                 "grado": str(d.get("grado", ""))[:100], "area": str(d.get("area", ""))[:60],
                 "tema": str(d.get("tema", ""))[:300]}
        pedido = urllib.request.Request(N8N, data=json.dumps({"s": SECRETO, "r": datos}).encode(),
                                        headers={"Content-Type": "application/json", "User-Agent": "curl/8.7.1"}, method="POST")
        try:
            with urllib.request.urlopen(pedido, timeout=30) as r:
                ok = json.loads(r.read() or b"{}").get("object") == "page"
        except Exception:
            ok = False
        responder(self, {"ok": ok}, 200 if ok else 502)
