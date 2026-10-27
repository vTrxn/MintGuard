import sys
import json
import uuid
import argparse
import urllib.request
import os

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "pii-sentinel"

class Sentinel:
    def __init__(self, model_name: str = MODEL_NAME, ollama_url: str = OLLAMA_URL):
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.vault = {}

    def _query_slm(self, text: str) -> dict:
        payload = {
            "model": self.model_name,
            "prompt": text,
            "stream": False,
            "options": {
                "temperature": 0.1
            }
        }
        req = urllib.request.Request(
            self.ollama_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                raw = data.get("response", "").strip()
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return {
                        "is_prompt_injection": True,
                        "injection_reason": "Output format violation / non-JSON escape attempt",
                        "entities": [],
                        "sanitized_text": text
                    }
        except urllib.error.URLError as e:
            raise RuntimeError(f"No se pudo conectar a Ollama en {self.ollama_url}. ¿Está corriendo el servicio? ({e})")

    def sanitize(self, text: str) -> dict:
        analysis = self._query_slm(text)
        
        if analysis.get("is_prompt_injection", False):
            return {
                "is_prompt_injection": True,
                "injection_reason": analysis.get("injection_reason", "Security policy violation"),
                "sanitized_text": text,
                "entities": [],
                "vault_id": None
            }

        session_id = str(uuid.uuid4())
        entities = analysis.get("entities", [])
        mapping = {ent["placeholder"]: ent["original"] for ent in entities if "placeholder" in ent}
        self.vault[session_id] = mapping

        return {
            "is_prompt_injection": False,
            "injection_reason": None,
            "sanitized_text": analysis.get("sanitized_text", text),
            "entities": entities,
            "vault_id": session_id
        }

    def rehydrate(self, vault_id: str, text: str) -> str:
        mapping = self.vault.get(vault_id, {})
        restored = text
        for placeholder, original in mapping.items():
            restored = restored.replace(placeholder, original)
        return restored

def run_interactive():
    guard = Sentinel()
    print("=" * 65)
    print("  CENTINELA SLM - MODO CONSOLA INTERACTIVA (Escribe 'salir' para terminar)")
    print("=" * 65)
    
    while True:
        try:
            user_input = input("\n[Entrada] > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("salir", "exit", "quit"):
                print("Cerrando sesión.")
                break

            result = guard.sanitize(user_input)
            
            if result["is_prompt_injection"]:
                print("\n\033[91m[!] ALERTA DE SEGURIDAD: INYECCIÓN DETECTADA\033[0m")
                print(f"    Motivo: {result['injection_reason']}")
                print("    Acción: Tráfico bloqueado.")
            else:
                print("\n\033[92m[✓] TRÁFICO SEGURO\033[0m")
                print(f"    Texto sanitizado: {result['sanitized_text']}")
                if result["entities"]:
                    print("    Entidades enmascaradas en Vault local:")
                    for ent in result["entities"]:
                        print(f"      • {ent.get('placeholder', '-')} -> {ent.get('original')} ({ent.get('type')})")
                else:
                    print("    (Sin datos sensibles detectados)")

        except KeyboardInterrupt:
            print("\nCerrando.")
            break
        except Exception as e:
            print(f"[Error]: {e}")

def process_file(file_path: str):
    if not os.path.isfile(file_path):
        print(f"Error: El archivo '{file_path}' no existe.")
        return

    guard = Sentinel()
    print(f"Procesando archivo: {file_path} ...")
    
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    lines = content.splitlines()
    sanitized_lines = []
    injections_found = 0
    total_entities = 0

    for idx, line in enumerate(lines):
        if not line.strip():
            sanitized_lines.append(line)
            continue
        res = guard.sanitize(line)
        if res["is_prompt_injection"]:
            injections_found += 1
            sanitized_lines.append(f"[BLOQUEADO POR SEGURIDAD: {res['injection_reason']}]")
        else:
            total_entities += len(res["entities"])
            sanitized_lines.append(res["sanitized_text"])

    base, ext = os.path.splitext(file_path)
    output_path = f"{base}_sanitized{ext}"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sanitized_lines))

    print("\nProceso finalizado:")
    print(f" - Archivo resultante guardado en: {output_path}")
    print(f" - Entidades sensibles anonimizadas: {total_entities}")
    print(f" - Inyecciones/Amenazas bloqueadas: {injections_found}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Centinela SLM - Herramienta de Privacidad y Seguridad")
    parser.add_argument("text", nargs="?", help="Texto a sanitizar de forma directa")
    parser.add_argument("--file", "-f", help="Ruta a un archivo de texto/logs para sanitizar por completo")
    args = parser.parse_args()

    if args.file:
        process_file(args.file)
    elif args.text:
        guard = Sentinel()
        res = guard.sanitize(args.text)
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        run_interactive()
