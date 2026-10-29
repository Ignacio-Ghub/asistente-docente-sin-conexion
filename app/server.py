"""Tiza sin conexión: servidor local.

Corre en la laptop de la escuela y sirve Tiza a los teléfonos de los docentes por la
red Wi-Fi local. No usa internet: el modelo de lenguaje corre en el mismo equipo con
Ollama. Usa la misma aplicación y la misma lógica que la versión web (carpeta web/),
solo cambia dónde corre el modelo. Solo usa la biblioteca estándar de Python.

Uso:  python3 app/server.py            (puerto 8080, abierto a la red local)
      MODELO=gemma4:e2b-it-qat python3 app/server.py
"""
import importlib.util
import json
import os
import socket
import sys
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
WEB = RAIZ.parent / "web"
DATOS = RAIZ / "datos"  # opiniones y perfiles; nunca salen del equipo
PUERTO = int(os.environ.get("PUERTO", "8080"))

os.environ["MOTOR"] = "local"
os.environ.setdefault("CODIGO_ACCESO", "aula2026")
sys.path.insert(0, str(WEB / "api"))

from _asistente import CODIGO, MODELO_LOCAL, responder  # noqa: E402


def funcion(nombre):
    spec = importlib.util.spec_from_file_location(nombre, WEB / "api" / "{}.py".format(nombre))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.handler


FUNCIONES = {n: funcion(n) for n in ("estado", "plan", "evaluacion", "repaso")}


class Tiza(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(WEB / "public"), **k)

    def log_message(self, fmt, *args):
        pass

    def guardar_local(self, nombre):
        """Sin internet, la opinión y el perfil se guardan en la laptop en vez de enviarse."""
        if self.headers.get("X-Codigo", "").strip().lower() != CODIGO.lower():
            return responder(self, {"ok": False, "error": "Contraseña incorrecta."}, 401)
        try:
            d = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 20_000)) or b"{}")
        except ValueError:
            return responder(self, {"ok": False}, 400)
        DATOS.mkdir(exist_ok=True)
        with open(DATOS / "{}.jsonl".format(nombre), "a", encoding="utf-8") as f:
            f.write(json.dumps({"fecha": datetime.now().isoformat(timespec="seconds"), **d}, ensure_ascii=False) + "\n")
        responder(self, {"ok": True})

    def api(self, metodo):
        nombre = self.path.split("?")[0][len("/api/"):]
        if metodo == "do_POST" and nombre in ("opinion", "perfil"):
            return self.guardar_local(nombre)
        h = FUNCIONES.get(nombre)
        if not h or not hasattr(h, metodo):
            return responder(self, {"error": "No existe."}, 404)
        if hasattr(h, "accion"):
            self.accion = lambda d: h.accion(self, d)
        getattr(h, metodo)(self)

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self.api("do_GET")
        super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            return self.api("do_POST")
        responder(self, {"error": "No existe."}, 404)


def ip_local():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no envía nada; solo elige la interfaz de la red local
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


if __name__ == "__main__":
    print("Tiza sin conexión en http://{}:{}  (modelo {}, contraseña {})".format(ip_local(), PUERTO, MODELO_LOCAL, CODIGO))
    ThreadingHTTPServer(("0.0.0.0", PUERTO), Tiza).serve_forever()
