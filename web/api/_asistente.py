"""Asistente docente: versión web de prueba (Vercel).

Misma lógica de planes y evaluaciones que la versión sin conexión, pero el modelo
corre en la nube (Claude Haiku 5.5) para que los docentes prueben la herramienta
desde su teléfono, a cualquier hora. Los guardados y el seguimiento quedan en el
navegador del teléfono; este servidor no guarda nada.
"""
import json
import re
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
    "condiciones del aula (sin electricidad, sin internet, sin fotocopias) y propone solo lo que "
    "se puede hacer con ellas. 5) Instrucciones concretas que el docente pueda aplicar "
    "mañana: tiempos, organización del grupo, qué dice y qué hace. 6) No inventes datos "
    "ni cifras. 7) Háblale al docente con naturalidad: no menciones cómo recibiste la información, ni "
    "copias, documentos adjuntos o textos cortados; si un contenido no aparece en los oficiales, dilo en una "
    "frase sencilla, por ejemplo «Este tema no aparece tal cual en el programa oficial de su grado; estos son "
    "los contenidos más cercanos». 8) Los minutos de inicio, desarrollo y cierre suman exactamente la duración "
    "de la clase. 9) Trata siempre al docente de usted (pida, escriba, observe), nunca de tú. Formato: frases claras y "
    "cortas; sin emojis, sin saludos, sin LaTeX (fracciones como 1/2)."
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
    return "Fuente: {}\n{}".format(datos["fuentes"][area], texto[:30000])


class Rechazo(Exception):
    """El modelo declinó la petición."""


def ejemplo_de(esquema):
    """Respuesta de relleno con la forma del esquema, para revisar la pantalla sin gastar en el modelo."""
    if esquema["type"] == "object":
        return {k: ejemplo_de(v) for k, v in esquema["properties"].items()}
    if esquema["type"] == "array":
        return [ejemplo_de(esquema["items"]) for _ in range(2)]
    if esquema["type"] == "integer":
        return 10
    if esquema["type"] == "boolean":
        return True
    return "Texto de prueba (modo sin modelo)."


def preguntar_modelo(prompt, sistema=SISTEMA, esquema=None, esfuerzo=None):
    if SIMULAR:
        if esquema is ESQUEMA_REVISION:
            return json.dumps({"revision": []})
        if esquema:
            return json.dumps(ejemplo_de(esquema))
        return "Modo de prueba de pantalla: este texto no lo escribió ningún modelo."
    import anthropic  # solo hace falta cuando hay modelo
    pedido = {
        "model": MODELO,
        "max_tokens": 16000,
        "system": sistema,
        "messages": [{"role": "user", "content": prompt}],
        "output_config": {"effort": esfuerzo or ("low" if esquema is None else "medium")},
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
    if d.get("multigrado") and grados_del_aula(d):
        for g in grados_del_aula(d):
            cur = curriculo_de(nivel, g, d.get("area", ""))
            if cur:
                base += ("\nContenidos y aprendizajes esperados oficiales del MPPE para esta área en "
                         + g + " (elige los que corresponden al tema):\n" + cur + "\n")
        return base
    cur = curriculo_de(nivel, d.get("grado", ""), d.get("area", ""))
    if cur:
        base += ("\nContenidos y aprendizajes esperados oficiales del MPPE para esta área y grado "
                 "(elige de aquí los que corresponden al tema):\n" + cur + "\n")
    return base


ORDINAL = {"1": "1er", "2": "2do", "3": "3er", "4": "4to", "5": "5to", "6": "6to"}


def grados_del_aula(d):
    """Grados de un aula multigrado a partir del texto del docente (ej.: «1er, 2do y 3er grado»)."""
    unidad = "año" if d.get("nivel") == "Media General" else "grado"
    numeros = re.findall(r"([1-6])\s*(?:er|ro|do|to|vo|º|°|\.?º)?", d.get("grados_multi", ""))
    vistos = []
    for n in numeros:
        g = "{} {}".format(ORDINAL[n], unidad)
        if g not in vistos:
            vistos.append(g)
    return vistos


# Las respuestas llegan ordenadas por partes (salida estructurada) para mostrarlas en tarjetas y tablas
# que el docente revisa de un vistazo. Con las mismas partes se arma el texto para compartir y guardar.
TEXTO = {"type": "string"}
LISTA = {"type": "array", "items": TEXTO}


def objeto(**campos):
    return {"type": "object", "properties": campos, "required": list(campos), "additionalProperties": False}


ESQUEMA_PLAN = objeto(
    titulo=TEXTO, nota_programa=TEXTO, proposito=TEXTO, contenidos=LISTA, materiales=LISTA,
    momentos={"type": "array", "items": objeto(nombre=TEXTO, minutos={"type": "integer"}, pasos=LISTA)},
    otras={"type": "array", "items": objeto(titulo=TEXTO, puntos=LISTA)})
ESQUEMA_EVALUACION = objeto(
    titulo=TEXTO, nota_programa=TEXTO, como_aplicarla=TEXTO,
    preguntas={"type": "array", "items": objeto(numero={"type": "integer"}, tipo=TEXTO, pregunta=TEXTO,
                                                 respuesta_esperada=TEXTO, si_falla=TEXTO)})
ESQUEMA_OBSERVACION = objeto(
    titulo=TEXTO, como_aplicarla=TEXTO,
    criterios={"type": "array", "items": objeto(criterio=TEXTO, logrado=TEXTO, en_proceso=TEXTO, necesita_apoyo=TEXTO)},
    preguntas_orales=LISTA)
ESQUEMA_REPASO = objeto(
    titulo=TEXTO, ideas_clave=LISTA, ejemplo=objeto(enunciado=TEXTO, pasos=LISTA),
    errores={"type": "array", "items": objeto(error=TEXTO, como_ayudar=TEXTO)},
    preguntas={"type": "array", "items": objeto(pregunta=TEXTO, respuesta=TEXTO)})

FORMATO = ("\nResponde en el formato estructurado pedido. Dentro de cada texto no uses asteriscos, "
           "almohadillas ni numeración propia: cada paso o punto va en su propio elemento de la lista.")
NOTA_PROGRAMA = ("En «nota_programa» escribe una frase solo si el tema no aparece tal cual en el programa "
                 "oficial de su grado (y cuáles son los contenidos más cercanos); si aparece, déjalo vacío.\n")


def prompt_plan(d):
    extra = ""
    if d.get("multigrado"):
        extra = ("Es un aula multigrado: propone una actividad común y luego tareas "
                 "diferenciadas por grado que se puedan hacer al mismo tiempo, con "
                 "estudiantes mayores apoyando a los menores (empieza esos pasos con el grado, "
                 "por ejemplo «3er grado: …»).\n")
    if es_educacion_fisica(d.get("area", "")):
        partes = ("- momentos: «Calentamiento», «Parte principal» (2 o 3 actividades con organización, reglas "
                  "y una variante más fácil y otra más difícil) y «Vuelta a la calma» (estiramiento y reflexión breve).\n"
                  "- otras: «Seguridad e inclusión», «Qué observar para evaluar» y «Para casa» (una actividad "
                  "física sencilla que se pueda hacer de día, sin electricidad).\n")
    else:
        partes = ("- momentos: «Inicio» (pregunta o situación que despierte interés), «Desarrollo» (actividades "
                  "paso a paso, con organización del grupo) y «Cierre» (cómo comprueba el docente lo que aprendieron).\n"
                  "- otras: «Para quien va atrasado» (una idea de refuerzo) y «Tarea para casa sin electricidad» "
                  "(breve, para hacer de día, sin internet y con lo que hay en cualquier casa).\n")
    extra += modo_clase(d)
    return (contexto_clase(d) + extra +
            "\nEscribe un borrador de plan de clase breve:\n"
            "- titulo: «Plan de clase: » y el tema.\n- proposito: una frase, qué podrán hacer al final.\n"
            "- contenidos: los contenidos del programa oficial que se trabajan (cítalos si están arriba).\n"
            "- materiales: lo que hace falta, solo lo disponible.\n" + partes +
            "Cada momento lleva sus minutos; los pasos dicen qué hace y qué dice el docente.\n" +
            NOTA_PROGRAMA + FORMATO)


def modo_clase(d):
    """Clase corta o de recuperación: los cortes de electricidad acortan y hacen perder clases."""
    tipo = d.get("tipo_clase", "normal")
    if tipo == "corta":
        return ("Es una clase corta (cortes de electricidad u horario reducido): trabaja solo lo esencial "
                "del contenido, con una actividad principal y un cierre rápido para comprobar lo aprendido.\n")
    if tipo == "recuperar":
        return ("El grupo perdió {n} clases de esta área (por cortes de electricidad u otras causas) y el "
                "tema indica lo que quedó pendiente. Propón cómo recuperarlo en esta clase: empieza con una "
                "comprobación rápida de lo que ya saben, prioriza los contenidos que son base para lo que "
                "sigue, junta lo que se pueda trabajar a la vez e indica qué se puede retomar más adelante "
                "o dejar como práctica en casa.\n").format(n=d.get("clases_perdidas") or "varias")
    return ""


def prompt_repaso(d):
    return (contexto_clase(d) +
            "\nEl docente quiere repasar este contenido antes de dar la clase (puede que no sea su "
            "especialidad). Escribe un repaso breve:\n"
            "- titulo: «Repaso: » y el tema.\n"
            "- ideas_clave: lo esencial del tema, explicado con sencillez y con exactitud (3 a 5 ideas).\n"
            "- ejemplo: un ejemplo adecuado al grado, resuelto paso a paso.\n"
            "- errores: errores frecuentes de los estudiantes y cómo ayudarlos a corregirlos (2 o 3).\n"
            "- preguntas: tres preguntas que suelen hacer los estudiantes, con una respuesta corta.\n"
            "Si no estás seguro de un dato, no lo incluyas. No escribas un plan de clase." + FORMATO)


def prompt_evaluacion(d):
    if es_educacion_fisica(d.get("area", "")):
        return (contexto_clase(d) +
                "\nCrea una lista de observación para evaluar esta clase práctica:\n"
                "- titulo: «Lista de observación: » y el tema.\n"
                "- como_aplicarla: una frase sobre cuándo y cómo observar.\n"
                "- criterios: 5 criterios observables (qué hace el estudiante), cada uno con lo que se ve en "
                "«logrado», «en proceso» y «necesita apoyo», en una frase cada nivel.\n"
                "- preguntas_orales: 2 preguntas breves para la reflexión final.\n"
                "No repitas el plan de clase." + FORMATO)
    return (contexto_clase(d) +
            "\nCrea una evaluación corta de 5 preguntas sobre el tema, para hacerla en voz alta o copiarla "
            "en la pizarra (sin fotocopias), adecuada al grado:\n"
            "- titulo: «Evaluación: » y el tema.\n"
            "- como_aplicarla: una frase sobre cómo hacerla (en voz alta, en la pizarra, en el cuaderno).\n"
            "- preguntas: 5, numeradas del 1 al 5. Tipo: 2 «Recordar», 2 «Aplicar» (a una situación concreta) "
            "y 1 «Explicar» (con sus palabras). En respuesta_esperada van todas las respuestas válidas; en "
            "si_falla, qué error indica que el estudiante necesita refuerzo y qué reforzar.\n" +
            NOTA_PROGRAMA + "No repitas el plan de clase." + FORMATO)


def texto_de(tipo, r):
    """Texto limpio del resultado, para compartir por WhatsApp (títulos en *negrita*) y para revisar la clave."""
    n = lambda t: "*{}*".format(t)
    l = [n(r.get("titulo", ""))]
    if r.get("nota_programa"):
        l += ["", r["nota_programa"]]
    if tipo == "plan":
        l += ["", n("Propósito:") + " " + r.get("proposito", "")]
        if r.get("contenidos"):
            l += ["", n("Contenidos del programa")] + ["- " + x for x in r["contenidos"]]
        if r.get("materiales"):
            l += ["", n("Materiales:") + " " + ", ".join(r["materiales"])]
        for m in r.get("momentos", []):
            l += ["", n("{} ({} minutos)".format(m["nombre"], m["minutos"]))]
            l += ["{}. {}".format(i, p) for i, p in enumerate(m["pasos"], 1)]
        for o in r.get("otras", []):
            l += ["", n(o["titulo"])] + ["- " + p for p in o["puntos"]]
    elif tipo == "evaluacion" and "criterios" in r:
        l += ["", r.get("como_aplicarla", "")]
        for i, c in enumerate(r["criterios"], 1):
            l += ["", n("{}. {}".format(i, c["criterio"])), "Logrado: " + c["logrado"],
                  "En proceso: " + c["en_proceso"], "Necesita apoyo: " + c["necesita_apoyo"]]
        l += ["", n("Preguntas para la reflexión")] + ["- " + p for p in r.get("preguntas_orales", [])]
    elif tipo == "evaluacion":
        l += ["", r.get("como_aplicarla", ""), "", n("Preguntas")]
        l += ["{}. ({}) {}".format(p["numero"], p["tipo"], p["pregunta"]) for p in r.get("preguntas", [])]
        l += ["", n("Clave para el docente")]
        for p in r.get("preguntas", []):
            l += ["{}. Respuesta esperada: {}".format(p["numero"], p["respuesta_esperada"]),
                  "   Si responde mal, reforzar: " + p["si_falla"]]
    else:
        l += ["", n("Lo esencial")] + ["- " + x for x in r.get("ideas_clave", [])]
        ej = r.get("ejemplo") or {}
        l += ["", n("Ejemplo:") + " " + ej.get("enunciado", "")] + ["{}. {}".format(i, p) for i, p in enumerate(ej.get("pasos", []), 1)]
        l += ["", n("Errores frecuentes")] + ["- {} Cómo ayudar: {}".format(e["error"], e["como_ayudar"]) for e in r.get("errores", [])]
        l += ["", n("Preguntas de los estudiantes")] + ["- {} {}".format(p["pregunta"], p["respuesta"]) for p in r.get("preguntas", [])]
    return "\n".join(l).strip()


def generar(tipo, d):
    """Pide el borrador ordenado por partes y devuelve las partes y su texto."""
    if tipo == "plan":
        prompt, esquema = prompt_plan(d), ESQUEMA_PLAN
    elif tipo == "repaso":
        prompt, esquema = prompt_repaso(d), ESQUEMA_REPASO
    elif es_educacion_fisica(d.get("area", "")):
        prompt, esquema = prompt_evaluacion(d), ESQUEMA_OBSERVACION
    else:
        prompt, esquema = prompt_evaluacion(d), ESQUEMA_EVALUACION
    partes = json.loads(preguntar_modelo(prompt, esquema=esquema, esfuerzo="low"))
    return {"partes": partes, "texto": texto_de(tipo, partes), "curriculo": d["_curriculo"]}


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
            return responder(self, {"error": "Contraseña incorrecta.", "codigo": True}, 401)
        largo = int(self.headers.get("Content-Length", 0))
        try:
            d = json.loads(self.rfile.read(largo) or b"{}")
            cur = curriculo_de(d.get("nivel", "Primaria"), d.get("grado", ""), d.get("area", ""))
            d["_curriculo"] = None if cur is None else "contenidos"
            return responder(self, self.accion(d))
        except Rechazo:
            return responder(self, {"error": "El asistente no pudo responder a este pedido. "
                                             "Prueba a escribir el tema de otra forma."}, 422)
        except (KeyError, ValueError) as e:
            return responder(self, {"error": "Datos incompletos: {}".format(e)}, 400)
        except Exception:
            return responder(self, {"error": "El asistente no está disponible en este momento. "
                                             "Intenta de nuevo en unos minutos."}, 503)
