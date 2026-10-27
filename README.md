# MintGuard

On-premises privacy gateway and prompt-injection guardrail powered by a fine-tuned 1.5B parameter language model (Qwen 2.5).

MintGuard runs locally to inspect incoming text, mask sensitive entities (PII, credentials, financial identifiers), detect adversarial prompt injections, and restore original values upon response completion. No unmasked data leaves the local environment.

Version: 1.0.0

---

## Architecture

```
User / Client Application
          │
          │ (1) Raw text with sensitive data
          ▼
┌──────────────────────────────────────────────┐
│ MintGuard Gateway (Local Inbound)            │
│                                              │
│ 1. SLM Guardrail (Qwen 2.5 1.5B Q4_K_M)      │
│    - Classifies prompt injection attacks     │
│    - Extracts PII, secrets, and financial ID │
│                                              │
│ 2. Ephemeral Token Vault (Local Memory)      │
│    - Stores: <NAME_1> -> "Carlos Pérez"      │
│    - Stores: <SECRET_1> -> "sk-proj-..."     │
└──────────────────────┬───────────────────────┘
                       │
                       │ (2) Sanitized text (<NAME_1>, <SECRET_1>)
                       ▼
             External Model / Cloud API
             (OpenAI, Anthropic, Gemini)
                       │
                       │ (3) Completion with placeholders
                       ▼
┌──────────────────────────────────────────────┐
│ MintGuard Gateway (Local Outbound)           │
│                                              │
│ 3. Rehydration Engine                        │
│    - Swaps placeholders with Vault values    │
└──────────────────────┬───────────────────────┘
                       │
                       │ (4) Final response restored
                       ▼
User / Client Application
```

---

## Core Capabilities

- **Strict Schema Enforcement:** Output is constrained to deterministic JSON containing classification status, injection reasoning, entity records, and sanitized text.
- **Entity Masking:** Identifies names (`NAME`), national IDs/passports (`ID`), contact details (`CONTACT`), API tokens/keys (`SECRET`), and banking/card numbers (`FINANCIAL`).
- **Prompt Injection Defense:** Detects privilege escalation, system override instructions, DAN roleplay exploits, and context delimiter hijacking.
- **Local Execution:** Operates entirely within your local hardware or private VPC using Ollama or `llama.cpp`. Quantized footprint is under 1.0 GB VRAM.
- **Deterministic Rehydration:** Ephemeral mapping ensures downstream cloud providers process abstractions while users receive intact natural responses.

---

## Project Structure

```
├── Modelfile             # Ollama configuration and system prompt definition
├── sentinel.py           # Standalone CLI, file processor, and Python SDK
├── proxy.py              # HTTP proxy service with /sanitize and /rehydrate endpoints
├── train.py              # Fine-tuning script using Unsloth and QLoRA
├── generate_dataset.py   # Synthetic dataset generator with adversarial distributions
├── test_model.py         # Automated evaluation suite for validation testing
├── train.jsonl           # Curated training dataset (420 records)
├── val.jsonl             # Hold-out validation dataset (75 records)
└── requirements.txt      # Project dependencies
```

---

## Model Specifications

| Parameter | Specification |
| :--- | :--- |
| **Base Architecture** | Qwen 2.5 (1.5B Instruct) |
| **Fine-Tuning Method** | QLoRA (r=16, alpha=16) via Unsloth |
| **Quantization Format** | GGUF (Q4_K_M) |
| **File Size** | ~986 MB |
| **Inference Hardware** | Consumer GPU (RTX 4060, RTX 3060, or Apple Silicon) / CPU fallback |
| **Inference Latency** | ~20–45 ms on CUDA Tensor Cores |

---

## Quickstart

### 1. Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/) installed and running locally.

### 2. Register the Model in Ollama

Place the compiled GGUF model file into the project root and run:

```bash
ollama create pii-sentinel -f Modelfile
```

Verify registration:

```bash
ollama list
```

### 3. Usage Options

#### Option A: Command Line Interface (CLI)

Single text analysis:

```bash
python sentinel.py "Dr. Sergio Morales, phone +34 655443322. Please update the record."
```

Interactive terminal mode:

```bash
python sentinel.py
```

Batch file processing (logs, CSVs, transcripts):

```bash
python sentinel.py --file path/to/access.log
```
*Generates `access_sanitized.log` with all sensitive entities masked.*

#### Option B: Python SDK

```python
from sentinel import Sentinel

guard = Sentinel()

# 1. Sanitize incoming request
result = guard.sanitize("Developer test: api_key is sk-proj-998877abc")

if result["is_prompt_injection"]:
    raise ValueError(f"Blocked: {result['injection_reason']}")

print("Safe payload:", result["sanitized_text"])
# Safe payload: Developer test: api_key is <SECRET_1>

# 2. Rehydrate after external completion
restored = guard.rehydrate(
    vault_id=result["vault_id"],
    text="Key <SECRET_1> has been successfully verified."
)
print("Delivered to user:", restored)
```

#### Option C: HTTP Gateway Service

Start the local server:

```bash
python proxy.py
```

Endpoints:
- `POST /sanitize`: Evaluates text, returns `{ blocked, sanitized_text, vault_id, raw_entities }`.
- `POST /rehydrate`: Replaces stored placeholders using the provided `vault_id`.
- `GET /`: Local monitoring and inspection interface.

---

## Evaluation & Benchmarks

Results tested across 75 out-of-sample validation records:

| Metric | Result | Description |
| :--- | :--- | :--- |
| **JSON Validity Rate** | 100.0% | Output parses via `json.loads` without formatting errors |
| **Schema Conformance** | 98.7% | Matches Pydantic validation types exactly |
| **PII Precision** | 97.4% | Accurate entity extraction across name, contact, secret, financial |
| **False Positive Rate** | 0.0% | Benign operational queries remained unmodified |
| **Attack Deflection** | 96.0% | Jailbreaks and override attempts blocked at ingestion |

---

## Retraining Pipeline

To reproduce the model from scratch:

1. Generate or update training records:
   ```bash
   python generate_dataset.py
   ```
2. Run `train.py` on a CUDA-enabled GPU (e.g. Google Colab T4 or local RTX GPU).
3. The script compiles and exports `Qwen2.5-1.5B-Instruct.Q4_K_M.gguf` ready for Ollama ingestion.

---

## License

MIT License. See LICENSE for details.
