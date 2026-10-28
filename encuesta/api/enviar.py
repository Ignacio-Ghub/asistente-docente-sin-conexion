"""Recibe una respuesta de la encuesta y la reenvía a n8n, que la guarda en Notion.

La clave compartida con n8n vive solo aquí (variable FORM_SECRETO), nunca en la página.
"""
import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler

N8N = "https://n8n.jibalab.com/webhook/jiba-encuesta-docentes-v1"
SECRETO = os.environ.get("FORM_SECRETO", "")


def responder(h, datos, codigo=200):
    cuerpo = json.dumps(datos, ensure_ascii=False).encode()
    h.send_response(codigo)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Content-Length", str(len(cuerpo)))
    h.end_headers()
    h.wfile.write(cuerpo)


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            largo = min(int(self.headers.get("Content-Length", 0)), 100_000)
            d = json.loads(self.rfile.read(largo) or b"{}")
        except ValueError:
            return responder(self, {"ok": False, "error": "Respuesta no válida."}, 400)
        if d.get("sitio_web"):  # campo trampa: solo lo llenan los robots
            return responder(self, {"ok": True})
        pedido = urllib.request.Request(
            N8N, data=json.dumps({"s": SECRETO, "r": d.get("r", {})}).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "curl/8.7.1"}, method="POST")
        try:
            with urllib.request.urlopen(pedido, timeout=40) as r:
                ok = json.loads(r.read() or b"{}").get("object") == "page"
        except Exception:
            ok = False
        if not ok:
            return responder(self, {"ok": False, "error": "No se pudo guardar la respuesta."}, 502)
        responder(self, {"ok": True})
