"""Asistente docente sin conexión: servidor local.

Corre en la laptop de la escuela y sirve la aplicación a los teléfonos de los
docentes por la red Wi-Fi local. No usa internet: el modelo de lenguaje corre en
el mismo equipo con Ollama. Solo usa la biblioteca estándar de Python.

Uso:  python3 server.py            (puerto 8080, abierto a la red local)
      MODELO=gemma4:e2b python3 server.py
"""
import json
import os
import socket
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DATOS = RAIZ / "datos"
REGISTRO = DATOS / "registro.json"  # estudiantes y resultados; nunca sale del equipo
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODELO = os.environ.get("MODELO", "gemma4:e4b-it-qat")
PUERTO = int(os.environ.get("PUERTO", "8080"))

# Regla de aviso temprano: simple y visible, sin IA, para que el docente la entienda.
UMBRAL = 0.6        # menos de 60 % de aciertos
EVALUACIONES = 2    # en las dos últimas evaluaciones

CURRICULO = RAIZ / "curriculo"

SISTEMA = (
    "Eres un asistente para docentes de escuelas rurales de Venezuela (estado Mérida). "
    "Escribes en español claro de Venezuela, como un colega con experiencia. Propones "
    "borradores que el docente revisa y decide. Reglas: 1) El plan responde exactamente "
    "al tema y al área que pide el docente; no lo conviertas en otra cosa. 2) Si hay "
    "contenidos del currículo oficial, básate en ellos y nómbralos; si no hay, no "
    "inventes normas ni contenidos oficiales. 3) Usa ejemplos de la vida local solo "
    "cuando ayuden de verdad al aprendizaje; no los fuerces. 4) Ten en cuenta las "
    "condiciones del aula (sin electricidad, sin internet, sin fotocopias) y propone solo lo que "
    "se puede hacer con ellas. 5) Instrucciones concretas que el docente pueda aplicar "
    "mañana: tiempos, organización del grupo, qué dice y qué hace. 6) No inventes datos "
    "ni cifras. Formato: texto simple con títulos y listas; sin emojis, sin saludos, sin "
    "LaTeX (fracciones como 1/2)."
)

# Orientaciones por área, tomadas del enfoque de cada área en el currículo oficial
# (documentos del MPPE para el año escolar vigente; Educación Física según el currículo de primaria).
ORIENTACION_AREA = {
    "educación física": (
        "Es una clase práctica de movimiento, no de pupitre ni de cuaderno. Estructura "
        "obligatoria: calentamiento (movilidad articular y activación), parte principal "
        "(ejercicios, juegos predeportivos o deportivos con reglas claras, organización "
        "en grupos, tiempos y variantes de dificultad) y vuelta a la calma (estiramiento, "
        "respiración y reflexión breve). Incluye medidas de seguridad (espacio, terreno, "
        "hidratación, frío) e inclusión de estudiantes con distintas capacidades. Si el "
        "tema une la actividad física con otra capacidad (por ejemplo, la atención o la "
        "concentración), explica en una frase por qué cada ejercicio la trabaja."),
    "matemática": (
        "Parte de una situación concreta, usa material manipulable o dibujos en la "
        "pizarra y pide a los estudiantes explicar cómo llegaron a la respuesta."),
    "lengua": (
        "Trabaja hablar, escuchar, leer y escribir con propósitos reales (contar, "
        "explicar, opinar, escribir una carta o un relato)."),
    "ciencias": (
        "Parte de la observación y de una pregunta que los estudiantes puedan "
        "investigar con lo que tienen a mano; registra lo observado."),
    "sociales": (
        "Vincula el tema con la historia, el territorio y la vida de la comunidad, "
        "con fuentes que tengan a mano (relatos de familiares, el entorno, el libro)."),
}


def orientacion_area(area):
    a = area.lower()
    if "física" in a or "deporte" in a:
        return ORIENTACION_AREA["educación física"]
    if "matemática" in a:
        return ORIENTACION_AREA["matemática"]
    if "lengua" in a:
        return ORIENTACION_AREA["lengua"]
    if "ciencias naturales" in a:
        return ORIENTACION_AREA["ciencias"]
    if "identidad" in a or "sociales" in a or "ciudadanía" in a:
        return ORIENTACION_AREA["sociales"]
    return ""


def es_educacion_fisica(area):
    a = area.lower()
    return "física" in a or "deporte" in a


def curriculo_de(nivel, grado, area):
    """Contenidos y aprendizajes esperados oficiales del área para ese grado o año; si no hay, None.

    Fuente: documentos del MPPE para el año escolar vigente (https://www.mppe.gob.ve/periodo-escolar-2025-2026/).
    """
    if not grado.strip():
        return None
    prefijo = "media" if nivel == "Media General" else "primaria"
    archivo = CURRICULO / "{}-{}.json".format(prefijo, grado.split()[0])
    if not archivo.exists():
        return None
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    texto = datos["areas"].get(area)
    if not texto:
        return None
    return "Fuente: {}\n{}".format(datos["fuentes"][area], texto[:14000])


def leer_registro():
    if REGISTRO.exists():
        return json.loads(REGISTRO.read_text(encoding="utf-8"))
    return {"estudiantes": [], "evaluaciones": []}


def escribir_json(ruta, datos):
    DATOS.mkdir(exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ruta)


def guardar_registro(reg):
    escribir_json(REGISTRO, reg)


GUARDADOS = DATOS / "guardados.json"  # planes y evaluaciones que el docente decidió guardar


def leer_guardados():
    if GUARDADOS.exists():
        return json.loads(GUARDADOS.read_text(encoding="utf-8"))
    return []


SIMULAR = os.environ.get("SIMULAR") == "1"  # solo para revisar la pantalla sin modelo


def preguntar_modelo(prompt, sistema=SISTEMA, formato=None, pensar=False):
    if SIMULAR:
        if formato:
            return json.dumps({"revision": []})
        return ("**Modo de prueba de pantalla:** este texto no lo escribió ningún modelo.\n"
                "1. Propósito de aprendizaje\n2. Inicio\n3. Desarrollo\n4. Cierre\n\n"
                "Datos recibidos:\n" + "\n".join("- " + l for l in prompt.splitlines()[:6]))
    pedido = {
        "model": MODELO,
        "stream": False,
        "think": pensar,  # sin razonamiento extra: respuestas más rápidas en equipos modestos
        "options": {"temperature": 0.2 if formato else 0.4, "num_ctx": 8192},
        "messages": [{"role": "system", "content": sistema},
                     {"role": "user", "content": prompt}],
    }
    if formato:
        pedido["format"] = formato
    cuerpo = json.dumps(pedido).encode()
    req = urllib.request.Request(OLLAMA + "/api/chat", data=cuerpo,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())["message"]["content"]


def contexto_clase(d):
    nivel = d.get("nivel", "Primaria")
    grados = d.get("grado", "")
    if d.get("multigrado"):
        grados = "aula multigrado con estudiantes de " + d.get("grados_multi", grados)
    base = (
        "Nivel: {nv}\nGrado o año: {g}\nÁrea: {a}\nTema: {t}\nNúmero de estudiantes: {n}\n"
        "Tiempo disponible: {m} minutos\nCondiciones: {c}\nMateriales disponibles: {mat}\n"
    ).format(nv=nivel, g=grados, a=d.get("area", ""), t=d.get("tema", ""),
             n=d.get("estudiantes", "no indicado"), m=d.get("minutos", 45),
             c=d.get("condiciones", "sin indicar"),
             mat=d.get("materiales") or "no indicados")
    orient = orientacion_area(d.get("area", ""))
    if orient:
        base += "\nOrientación del área: " + orient + "\n"
    cur = curriculo_de(nivel, d.get("grado", ""), d.get("area", ""))
    if cur:
        base += ("\nContenidos y aprendizajes esperados oficiales del MPPE para esta área y grado "
                 "(elige de aquí los que corresponden al tema):\n" + cur + "\n")
    return base


def prompt_plan(d):
    extra = ""
    if d.get("multigrado"):
        extra = ("Es un aula multigrado: propone una actividad común y luego tareas "
                 "diferenciadas por grado que se puedan hacer al mismo tiempo, con "
                 "estudiantes mayores apoyando a los menores.\n")
    if es_educacion_fisica(d.get("area", "")):
        partes = ("1. Propósito (una frase: qué lograrán).\n"
                  "2. Contenido del currículo que se trabaja (cítalo si está arriba).\n"
                  "3. Materiales y espacio.\n"
                  "4. Calentamiento (minutos y ejercicios).\n"
                  "5. Parte principal: 2 o 3 actividades con organización, reglas, "
                  "tiempos y una variante más fácil y otra más difícil.\n"
                  "6. Vuelta a la calma y reflexión.\n"
                  "7. Seguridad e inclusión.\n"
                  "8. Qué observar para evaluar.\n")
    else:
        partes = ("1. Propósito (una frase: qué podrán hacer al final).\n"
                  "2. Contenido del currículo que se trabaja (cítalo si está arriba).\n"
                  "3. Inicio: pregunta o situación que despierte interés.\n"
                  "4. Desarrollo: actividades paso a paso, con tiempos y organización.\n"
                  "5. Cierre: cómo comprueba el docente lo que aprendieron.\n"
                  "6. Para quien va atrasado: una idea de refuerzo.\n")
    return (contexto_clase(d) + extra +
            "\nEscribe un borrador de plan de clase breve con estas partes:\n" + partes +
            "Termina con: «Borrador para revisar y ajustar por el docente.»")


def prompt_evaluacion(d):
    if es_educacion_fisica(d.get("area", "")):
        return (contexto_clase(d) +
                "\nCrea una lista de observación para evaluar esta clase práctica: 5 "
                "criterios observables (qué hace el estudiante), cada uno con tres niveles "
                "(logrado, en proceso, necesita apoyo) descritos en una frase. Añade 2 "
                "preguntas orales breves para la reflexión final. Escribe solo la lista de "
                "observación y las preguntas; no repitas el plan de clase.")
    return (contexto_clase(d) +
            "\nCrea una evaluación corta de 5 preguntas sobre el tema, para hacerla en voz "
            "alta o copiarla en la pizarra (sin fotocopias), adecuada al grado. Mezcla: 2 "
            "preguntas de recordar, 2 de aplicar a una situación concreta y 1 de explicar "
            "con sus palabras. Después escribe «Clave para el docente:» con la respuesta "
            "esperada de cada una (todas las respuestas válidas) y qué error indica que el "
            "estudiante necesita refuerzo. Escribe solo la evaluación y la clave; no "
            "repitas el plan de clase.")


# Segunda capa de control: el modelo revisa la clave de respuestas antes de mostrarla.
# No corrige nada; solo marca lo dudoso para que el docente lo mire con atención.
REVISOR = (
    "Eres un revisor estricto de evaluaciones escolares de primaria. Para cada pregunta: "
    "1) comprueba que tenga sentido y se pueda responder; 2) resuélvela tú mismo y piensa "
    "en todas las respuestas correctas posibles, incluidos sinónimos; 3) compara con la respuesta esperada; 4) comprueba que el «error común» no "
    "sea en realidad una respuesta correcta. Marca correcta=false si falla cualquiera de "
    "los cuatro puntos. No opines sobre estilo ni dificultad."
)
ESQUEMA_REVISION = {
    "type": "object",
    "properties": {"revision": {"type": "array", "items": {
        "type": "object",
        "properties": {"pregunta": {"type": "integer"},
                       "correcta": {"type": "boolean"},
                       "motivo": {"type": "string"}},
        "required": ["pregunta", "correcta", "motivo"]}}},
    "required": ["revision"],
}


def revisar_clave(texto):
    prompt = ("Revisa esta evaluación y su clave. Para cada una de las 5 preguntas indica "
              "si la respuesta esperada y el error común son correctos. Si algo está mal, "
              "explica en una frase qué está mal y cuál sería lo correcto.\n\n" + texto)
    try:
        r = json.loads(preguntar_modelo(prompt, sistema=REVISOR,
                                        formato=ESQUEMA_REVISION, pensar=True))
        return [x for x in r.get("revision", []) if not x.get("correcta", True)]
    except (ValueError, KeyError):
        return None  # la revisión falló; la interfaz lo dice en vez de callar


def calcular_avisos(reg):
    avisos = []
    for est in reg["estudiantes"]:
        res = [e for e in reg["evaluaciones"] if e["estudiante"] == est["id"]]
        res.sort(key=lambda e: e["fecha"])
        ultimas = res[-EVALUACIONES:]
        if len(ultimas) < EVALUACIONES:
            continue
        if all(e["aciertos"] / e["total"] < UMBRAL for e in ultimas):
            avisos.append({
                "estudiante": est["nombre"],
                "grado": est.get("grado", ""),
                "detalle": ", ".join("{} {}/{}".format(e["tema"], e["aciertos"], e["total"])
                                     for e in ultimas),
            })
    return avisos


class Manejador(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(RAIZ / "web"), **k)

    def log_message(self, fmt, *args):
        pass

    def responder(self, datos, codigo=200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        if self.path == "/api/registro":
            reg = leer_registro()
            return self.responder({**reg, "avisos": calcular_avisos(reg),
                                   "regla": {"umbral": UMBRAL, "evaluaciones": EVALUACIONES}})
        if self.path == "/api/guardados":
            return self.responder(leer_guardados())
        if self.path == "/api/estado":
            if SIMULAR:
                return self.responder({"ok": False, "simulado": True, "modelo": MODELO})
            try:
                with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=3) as r:
                    modelos = [m["name"] for m in json.loads(r.read())["models"]]
                return self.responder({"ok": MODELO in modelos, "modelo": MODELO})
            except Exception:
                return self.responder({"ok": False, "modelo": MODELO})
        return super().do_GET()

    def do_POST(self):
        largo = int(self.headers.get("Content-Length", 0))
        d = json.loads(self.rfile.read(largo) or b"{}")
        try:
            cur = curriculo_de(d.get("nivel", "Primaria"), d.get("grado", ""), d.get("area", ""))
            curriculo = None if cur is None else "contenidos"
            if self.path == "/api/plan":
                return self.responder({"texto": preguntar_modelo(prompt_plan(d)),
                                       "curriculo": curriculo})
            if self.path == "/api/evaluacion":
                texto = preguntar_modelo(prompt_evaluacion(d))
                # Una lista de observación no tiene clave de respuestas que revisar.
                revision = "no_aplica" if es_educacion_fisica(d.get("area", "")) else revisar_clave(texto)
                return self.responder({"texto": texto, "revision": revision,
                                       "curriculo": curriculo})
            if self.path == "/api/guardar":
                docs = leer_guardados()
                docs.insert(0, {"id": max([x["id"] for x in docs] + [0]) + 1,
                                "titulo": d["titulo"], "tipo": d["tipo"],
                                "fecha": d["fecha"], "html": d["html"]})
                escribir_json(GUARDADOS, docs)
                return self.responder({"ok": True})
            if self.path == "/api/borrar":
                escribir_json(GUARDADOS, [x for x in leer_guardados() if x["id"] != int(d["id"])])
                return self.responder({"ok": True})
            if self.path == "/api/estudiante":
                reg = leer_registro()
                nuevo = {"id": max([e["id"] for e in reg["estudiantes"]] + [0]) + 1,
                         "nombre": d["nombre"].strip(), "grado": d.get("grado", "")}
                reg["estudiantes"].append(nuevo)
                guardar_registro(reg)
                return self.responder(nuevo)
            if self.path == "/api/resultados":
                reg = leer_registro()
                for r in d["resultados"]:
                    reg["evaluaciones"].append({
                        "estudiante": int(r["estudiante"]), "aciertos": int(r["aciertos"]),
                        "total": int(d["total"]), "tema": d["tema"], "fecha": d["fecha"]})
                guardar_registro(reg)
                return self.responder({"ok": True, "avisos": calcular_avisos(reg)})
        except urllib.error.URLError:
            return self.responder({"error": "El modelo local no responde. ¿Está encendido Ollama?"}, 503)
        except (KeyError, ValueError) as e:
            return self.responder({"error": "Datos incompletos: {}".format(e)}, 400)
        self.responder({"error": "Ruta desconocida"}, 404)


def ip_local():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no envía nada; solo elige la interfaz local
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


if __name__ == "__main__":
    print("Asistente docente en http://{}:{}  (modelo {})".format(ip_local(), PUERTO, MODELO))
    ThreadingHTTPServer(("0.0.0.0", PUERTO), Manejador).serve_forever()
