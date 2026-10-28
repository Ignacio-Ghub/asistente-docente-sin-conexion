"""Asistente docente: versión web de prueba (Vercel).

Misma lógica de planes y evaluaciones que la versión sin conexión, pero el modelo
corre en la nube (Claude Haiku 5.5) para que los docentes prueben la herramienta
desde su teléfono, a cualquier hora. Los guardados y el seguimiento quedan en el
navegador del teléfono; este servidor no guarda nada.
"""
import json
import os
from http.server import BaseHTTPRequestHandler
from pathlib import Path

CURRICULO = Path(__file__).resolve().parent / "curriculo"
MODELO = "claude-haiku-5-5"
CODIGO = os.environ.get("CODIGO_ACCESO", "")
SIMULAR = os.environ.get("SIMULAR") == "1"  # solo para revisar la pantalla sin modelo

SISTEMA = (
    "Eres un asistente para docentes de escuelas rurales de Venezuela (estado Mérida). "
    "Escribes en español claro de Venezuela, como un colega con experiencia. Propones "
    "borradores que el docente revisa y decide. Reglas: 1) El plan responde exactamente "
    "al tema y al área que pide el docente; no lo conviertas en otra cosa. 2) Si hay "
    "contenidos del currículo oficial, básate en ellos y nómbralos; si no hay, no "
    "inventes normas ni contenidos oficiales. 3) Usa ejemplos de la vida local solo "
    "cuando ayuden de verdad al aprendizaje; no los fuerces. 4) Ten en cuenta las "
    "condiciones del aula (sin luz, sin internet, sin fotocopias) y propone solo lo que "
    "se puede hacer con ellas. 5) Instrucciones concretas que el docente pueda aplicar "
    "mañana: tiempos, organización del grupo, qué dice y qué hace. 6) No inventes datos "
    "ni cifras. Formato: texto simple con títulos y listas; sin emojis, sin saludos, sin "
    "LaTeX (fracciones como 1/2)."
)

# Orientaciones por área, tomadas del enfoque de cada área en el currículo oficial
# (Primaria 2007 y cambio curricular de Media General 2015-2016).
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
    if "sociales" in a or "memoria" in a or "ciudadanía" in a:
        return ORIENTACION_AREA["sociales"]
    return ""


def es_educacion_fisica(area):
    a = area.lower()
    return "física" in a or "deporte" in a


def curriculo_de(nivel, grado, area):
    """Texto oficial del área para ese grado, si lo tenemos cargado; si no, None."""
    if nivel == "Media General":
        archivo = CURRICULO / "media-general.json"
    else:
        if not grado.strip():
            return None
        archivo = CURRICULO / "primaria-{}.json".format(grado.split()[0])
    if not archivo.exists():
        return None
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    texto = datos["areas"].get(area)
    if not texto:
        return None
    tipo = datos.get("tipo", "contenidos del grado")
    return "Fuente ({}): {}\n{}".format(tipo, datos["fuente"], texto[:6000])


class Rechazo(Exception):
    """El modelo declinó la petición."""


def preguntar_modelo(prompt, sistema=SISTEMA, esquema=None):
    if SIMULAR:
        if esquema:
            return json.dumps({"revision": []})
        return ("**Modo de prueba de pantalla:** este texto no lo escribió ningún modelo.\n"
                "1. Propósito de aprendizaje\n2. Inicio\n3. Desarrollo\n4. Cierre\n\n"
                "Datos recibidos:\n" + "\n".join("- " + l for l in prompt.splitlines()[:6]))
    import anthropic  # solo hace falta cuando hay modelo
    pedido = {
        "model": MODELO,
        "max_tokens": 16000,
        "system": sistema,
        "messages": [{"role": "user", "content": prompt}],
        "output_config": {"effort": "low" if esquema is None else "medium"},
    }
    if esquema:
        pedido["output_config"]["format"] = {"type": "json_schema", "schema": esquema}
    r = anthropic.Anthropic().messages.create(**pedido)
    if r.stop_reason == "refusal":
        raise Rechazo()
    return next(b.text for b in r.content if b.type == "text")


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
        base += ("\nCurrículo oficial de esta área y grado (elige de aquí los contenidos "
                 "que corresponden al tema):\n" + cur + "\n")
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
        "required": ["pregunta", "correcta", "motivo"],
        "additionalProperties": False}}},
    "required": ["revision"],
    "additionalProperties": False,
}


def revisar_clave(texto):
    prompt = ("Revisa esta evaluación y su clave. Para cada una de las 5 preguntas indica "
              "si la respuesta esperada y el error común son correctos. Si algo está mal, "
              "explica en una frase qué está mal y cuál sería lo correcto.\n\n" + texto)
    try:
        r = json.loads(preguntar_modelo(prompt, sistema=REVISOR, esquema=ESQUEMA_REVISION))
        return [x for x in r.get("revision", []) if not x.get("correcta", True)]
    except Exception:
        return None  # la revisión falló; la interfaz lo dice en vez de callar


def responder(h, datos, codigo=200):
    cuerpo = json.dumps(datos, ensure_ascii=False).encode()
    h.send_response(codigo)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Content-Length", str(len(cuerpo)))
    h.end_headers()
    h.wfile.write(cuerpo)


class Base(BaseHTTPRequestHandler):
    """Comprueba el código de acceso y convierte los errores en mensajes para el docente."""

    def accion(self, d):
        raise NotImplementedError

    def do_POST(self):
        if not CODIGO or self.headers.get("X-Codigo", "").strip().lower() != CODIGO.lower():
            return responder(self, {"error": "Código de acceso incorrecto.", "codigo": True}, 401)
        largo = int(self.headers.get("Content-Length", 0))
        try:
            d = json.loads(self.rfile.read(largo) or b"{}")
            cur = curriculo_de(d.get("nivel", "Primaria"), d.get("grado", ""), d.get("area", ""))
            d["_curriculo"] = None if cur is None else (
                "enfoque" if "enfoque del área" in cur else "contenidos")
            return responder(self, self.accion(d))
        except Rechazo:
            return responder(self, {"error": "El asistente no pudo responder a este pedido. "
                                             "Prueba a escribir el tema de otra forma."}, 422)
        except (KeyError, ValueError) as e:
            return responder(self, {"error": "Datos incompletos: {}".format(e)}, 400)
        except Exception:
            return responder(self, {"error": "El asistente no está disponible en este momento. "
                                             "Intenta de nuevo en unos minutos."}, 503)
