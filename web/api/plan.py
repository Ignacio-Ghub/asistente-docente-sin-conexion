from _asistente import Base, preguntar_modelo, prompt_plan


class handler(Base):
    def accion(self, d):
        return {"texto": preguntar_modelo(prompt_plan(d)), "curriculo": d["_curriculo"]}
