# Prototipo: asistente docente sin conexión

Funciona sin internet. Una laptop hace de servidor y los teléfonos de los docentes se conectan a ella por la red Wi-Fi local. No usa librerías externas, solo Python 3.

## Funciones
1. **Planificar:** propone un plan de clase según el nivel (Primaria de 1.º a 6.º grado o Media General de 1.º a 5.º año), el área, el tema, los materiales y las condiciones del aula. Admite aulas multigrado. Cada área tiene su propia estructura; Educación Física, por ejemplo, lleva calentamiento, parte principal, vuelta a la calma y medidas de seguridad.
2. **Evaluar:** crea 5 preguntas con su clave de respuestas, y una revisión automática marca las respuestas dudosas. En Educación Física crea en cambio una lista de observación.
3. **Seguimiento:** el docente anota los aciertos y aparece un aviso cuando un estudiante saca menos del 60 % en las dos últimas evaluaciones. El aviso sale de una regla simple, no de la IA.
4. **Guardados:** los planes y evaluaciones se guardan en el equipo y se pueden consultar sin electricidad ni internet. «Descargar archivo» crea una copia para imprimirla cuando haya electricidad.

## Contenidos oficiales cargados (carpeta `curriculo/`)
Fuente: documentos del Ministerio del Poder Popular para la Educación para el año escolar vigente, publicados en https://www.mppe.gob.ve/periodo-escolar-2025-2026/ («Propuestas de contenidos para la enseñanza y aprendizajes esperados»). Revisado el 28/10/2026.

| Área | Documento | Niveles |
|---|---|---|
| Prácticas del Lenguaje | Documento para la consulta, septiembre 2025 | 1.er a 6.º grado y 1.er a 5.º año |
| Matemática | Octubre 2026 | 1.er a 6.º grado y 1.er a 5.º año |
| Ciencias Naturales | Octubre 2026 | 1.er a 6.º grado y 1.er a 5.º año |
| Identidad | Documento para la consulta, septiembre 2025 | 1.er a 6.º grado y 1.er a 5.º año |

El plan cita los contenidos y aprendizajes esperados del grado o año. Educación Física y las demás áreas de Media General no tienen documento de contenidos publicado ahí: la pantalla lo avisa. Los archivos del currículo de 2007 que se usaban antes están archivados aparte.

## Instalar el modelo (una sola vez, con internet)
1. Descargar e instalar Ollama desde https://ollama.com/download (Mac o Windows).
2. En la Terminal, descargar el modelo. Pesa 6,1 GB y después ya no necesita internet:

```bash
ollama pull gemma4:e4b-it-qat
```

## Usar
```bash
python3 app/server.py
```
La pantalla muestra una dirección, por ejemplo `http://192.168.1.20:8080`. Los teléfonos conectados al mismo Wi-Fi la abren en el navegador.

- **Revisar solo la pantalla, sin modelo:** `SIMULAR=1 python3 app/server.py`.

## Pruebas del 27/10/2026 (Mac M4 Pro)
Las respuestas completas están en `../pruebas/`.

| Modelo | Disco | Plan de clase | Evaluación |
|---|---|---|---|
| gemma4:e4b-it-qat (**por defecto**) | 6,1 GB | 10-14 s | 9-12 s |

- **Calidad:** buen español, contexto del páramo bien usado, aulas multigrado bien resueltas.
- **Errores detectados:** en una evaluación del ciclo del agua, la clave marcó como error la respuesta «gas», que en realidad es correcta. Por eso la revisión del docente es indispensable, y así debe decirlo la solicitud.
- **Velocidad en equipos reales:** no está medida. Una laptop modesta, sin tarjeta gráfica, será bastante más lenta. Hay que medirla en un equipo como el de las escuelas.

También se compararon gemma4:e2b-it-qat, qwen3.5:4b, llama3.2:3b y phi4-mini. Gemma 4 E4B salió mejor. Llama y Phi cometieron errores graves en la clave. Solo quedó instalado Gemma 4 E4B.

### Segunda revisión de la clave (27/10)
Se probó con 3 claves que tenían errores conocidos y con 1 correcta. Tarda unos 25 segundos más por evaluación. En total, Evaluar tarda unos 30-35 segundos en un Mac M4 Pro.

| Clave | Error real | ¿Lo marcó? |
|---|---|---|
| Fracciones (Llama) | Pregunta 4: dice que se guardan 3/4 cuando se guarda 1/4 | Sí |
| Fracciones (Phi) | Pregunta 1 incoherente («papaya» y papas) | Sí (también marcó la pregunta 2, que es ambigua) |
| Ciclo del agua | Pregunta 1: marca «gas» como error y es correcto | **No** |
| Fracciones (Gemma) | Ninguno | No marcó nada (sin falsa alarma) |

Atrapa errores evidentes, pero no todos. Sigue siendo una ayuda, no una garantía. La revisión del docente no se reemplaza.

## Probarlo sin internet
**En el Mac**
1. En la Terminal, ejecuta `python3 app/server.py`.
2. Apaga el Wi-Fi.
3. Usa el asistente en el navegador (`http://localhost:8080`). Funciona igual, porque todo corre en el Mac.

**Con el teléfono**
El punto de acceso del iPhone necesita los datos móviles encendidos, así que no sirve para crear una red sin internet. La forma más sencilla es esta:
1. Conecta el Mac y el teléfono al Wi-Fi de tu casa.
2. Desconecta el cable de internet del router (el que viene de la calle) y deja el router encendido. El Wi-Fi sigue funcionando, pero sin internet. Es lo mismo que pasaría en la escuela con un router propio.
3. Ejecuta `python3 app/server.py`. En la Terminal aparece una dirección del tipo `http://192.168.1.20:8080`. Ábrela en el teléfono.
4. La primera vez, el Mac puede preguntar si permites conexiones entrantes a Python: acepta.

Prueba del 27/10: con el asistente funcionando, ni el asistente ni el modelo abrieron ninguna conexión hacia internet; solo usan el propio equipo.

## Pendiente
- Probar en una laptop modesta (8 GB, sin tarjeta gráfica) y medir los tiempos.
- Validar las áreas de aprendizaje con los docentes y con el documento curricular que usan hoy. Siguen la organización de la primaria bolivariana.
- Grabar la demo con el wifi apagado.
- Revisar con los docentes la calidad de 10-20 respuestas reales y anotar los errores.
