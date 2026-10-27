# MintGuard

Pasarela de privacidad y cortafuegos contra inyecciones de instrucciones (*prompt injection*) on-premise, impulsado por un modelo de lenguaje compacto (SLM) de 1.5B parámetros (Qwen 2.5).

MintGuard se ejecuta de forma local para inspeccionar texto entrante, enmascarar entidades confidenciales (datos personales, credenciales técnicas, identificadores financieros), neutralizar ataques adversariales y restaurar los valores originales cuando el modelo externo completa su respuesta. Ningún dato sensible sin anonimizar sale del entorno local.

Versión: 1.0.0

---

## Arquitectura

```
Usuario / Aplicación Cliente
          │
          │ (1) Texto entrante con datos confidenciales
          ▼
┌──────────────────────────────────────────────┐
│ MintGuard Gateway (Entrada Local)            │
│                                              │
│ 1. Centinela SLM (Qwen 2.5 1.5B Q4_K_M)      │
│    - Clasifica ataques de prompt injection   │
│    - Extrae PII, secretos y datos bancarios  │
│                                              │
│ 2. Token Vault Efímero (Memoria RAM Local)   │
│    - Guarda: <NAME_1> -> "Carlos Pérez"      │
│    - Guarda: <SECRET_1> -> "sk-proj-..."     │
└──────────────────────┬───────────────────────┘
                       │
                       │ (2) Texto sanitizado (<NAME_1>, <SECRET_1>)
                       ▼
              Modelo en la Nube / API
             (OpenAI, Anthropic, Gemini)
                       │
                       │ (3) Respuesta generada con etiquetas
                       ▼
┌──────────────────────────────────────────────┐
│ MintGuard Gateway (Salida Local)             │
│                                              │
│ 3. Motor de Re-hidratación                   │
│    - Restaura etiquetas con valores reales   │
└──────────────────────┬───────────────────────┘
                       │
                       │ (4) Respuesta final completa
                       ▼
Usuario / Aplicación Cliente
```

---

## Capacidades Principales

- **Cumplimiento estricto de esquema:** Salida forzada a un JSON determinista que contiene estado de seguridad, justificación del análisis, listado de entidades y texto sanitizado.
- **Enmascaramiento de entidades:** Identifica nombres (`NAME`), documentos de identidad o pasaportes (`ID`), datos de contacto (`CONTACT`), tokens y claves de API (`SECRET`), y números bancarios o tarjetas (`FINANCIAL`).
- **Defensa contra inyecciones de prompt:** Detecta simulaciones de modo desarrollador, instrucciones de anulación del sistema, *jailbreaks* estilo DAN y secuestro de delimitadores de contexto.
- **Ejecución 100% local:** Corre dentro de tu propia infraestructura o hardware con Ollama o `llama.cpp`. El modelo cuantizado consume menos de 1.0 GB de VRAM.
- **Re-hidratación determinista:** El mapeo temporal en memoria asegura que los proveedores de IA externos solo procesen abstracciones, mientras el usuario recibe respuestas naturales con sus datos reales.

---

## Estructura del Proyecto

```
├── Modelfile             # Definición del modelo y plantilla ChatML para Ollama
├── sentinel.py           # Herramienta CLI, procesador por lotes y SDK para Python
├── proxy.py              # Servicio HTTP local con endpoints /sanitize y /rehydrate
├── train.py              # Script de fine-tuning optimizado con Unsloth y QLoRA
├── generate_dataset.py   # Generador del dataset sintético equilibrado
├── test_model.py         # Suite de pruebas automatizada para validación
├── train.jsonl           # Dataset de entrenamiento (420 registros)
├── val.jsonl             # Dataset de validación fuera de muestra (75 registros)
└── requirements.txt      # Dependencias del proyecto
```

---

## Especificaciones del Modelo

| Parámetro | Especificación |
| :--- | :--- |
| **Arquitectura base** | Qwen 2.5 (1.5B Instruct) |
| **Método de Fine-Tuning** | QLoRA (r=16, alpha=16) mediante Unsloth |
| **Formato de cuantización** | GGUF (Q4_K_M) |
| **Tamaño de archivo** | ~986 MB |
| **Hardware de inferencia** | GPU de consumo (RTX 4060, RTX 3060, Apple Silicon) o CPU |
| **Latencia de inferencia** | ~20–45 ms en núcleos Tensor CUDA |

---

## Guía de Inicio Rápido

### 1. Requisitos

- Python 3.10 o superior.
- [Ollama](https://ollama.com/) instalado y activo en el sistema.

### 2. Registrar el Modelo en Ollama

Ubica el archivo compilado `.gguf` en la raíz del proyecto y ejecuta:

```bash
ollama create pii-sentinel -f Modelfile
```

Verifica el registro:

```bash
ollama list
```

### 3. Modos de Uso

#### Opción A: Interfaz de Línea de Comandos (CLI)

Análisis de un texto directo:

```bash
python sentinel.py "Dr. Sergio Morales, teléfono +34 655443322. Favor actualizar el registro."
```

Modo consola interactiva:

```bash
python sentinel.py
```

Procesamiento de archivos en lote (logs, CSVs, transcripciones):

```bash
python sentinel.py --file ruta/al/archivo.log
```
*Genera automáticamente `archivo_sanitized.log` con todas las entidades sensibles enmascaradas.*

#### Opción B: SDK en Python

```python
from sentinel import Sentinel

guard = Sentinel()

# 1. Sanitizar petición entrante
resultado = guard.sanitize("Prueba de depuración: api_key es sk-proj-998877abc")

if resultado["is_prompt_injection"]:
    raise ValueError(f"Bloqueado: {resultado['injection_reason']}")

print("Texto seguro:", resultado["sanitized_text"])
# Salida: Prueba de depuración: api_key es <SECRET_1>

# 2. Re-hidratar tras recibir respuesta externa
respuesta_final = guard.rehydrate(
    vault_id=resultado["vault_id"],
    text="La clave <SECRET_1> ha sido verificada correctamente."
)
print("Entregado al usuario:", respuesta_final)
```

#### Opción C: Servicio Gateway HTTP

Inicia el servidor local:

```bash
python proxy.py
```

Endpoints disponibles:
- `POST /sanitize`: Analiza el texto y retorna `{ blocked, sanitized_text, vault_id, raw_entities }`.
- `POST /rehydrate`: Reemplaza las etiquetas usando el `vault_id` de la sesión.
- `GET /`: Panel visual de inspección y monitorización local.

---

## Evaluación y Métricas de Rendimiento

Pruebas ejecutadas sobre 75 registros fuera de muestra (*out-of-sample*):

| Métrica | Resultado | Descripción |
| :--- | :--- | :--- |
| **Tasa de validez JSON** | 100.0% | Todas las respuestas parsean con `json.loads` sin errores sintácticos |
| **Conformidad de esquema** | 98.7% | Coincidencia exacta con los tipos definidos |
| **Precisión en PII** | 97.4% | Extracción precisa en nombres, contactos, secretos y datos bancarios |
| **Falsos positivos** | 0.0% | Consultas operativas benignas no sufrieron alteraciones |
| **Bloqueo de ataques** | 96.0% | Intentos de jailbreak y anulación interceptados en la entrada |

---

## Pipeline de Re-entrenamiento

Para reproducir el modelo desde cero:

1. Generar o ampliar el dataset:
   ```bash
   python generate_dataset.py
   ```
2. Ejecutar `train.py` en un entorno con GPU CUDA (por ejemplo, Google Colab con GPU T4 gratuita).
3. El script compila y exporta directamente `Qwen2.5-1.5B-Instruct.Q4_K_M.gguf`, listo para ser consumido por Ollama.

---

## Licencia

Distribuido bajo la Licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más información.
