from _asistente import Base, es_educacion_fisica, preguntar_modelo, prompt_evaluacion, revisar_clave


class handler(Base):
    def accion(self, d):
        texto = preguntar_modelo(prompt_evaluacion(d))
        # Una lista de observación no tiene clave de respuestas que revisar.
        revision = "no_aplica" if es_educacion_fisica(d.get("area", "")) else revisar_clave(texto)
        return {"texto": texto, "revision": revision, "curriculo": d["_curriculo"]}
