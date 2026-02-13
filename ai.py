#!/usr/bin/env python3
import os
import sys
import base64
import requests
import time

# --- DEFAULT FALLBACK MODELS ---
DEFAULT_MODELS = [
    "qwen/qwen-2.5-vl-7b-instruct:free",
    "meta-llama/llama-3.2-11b-vision-instruct",
    "google/gemini-2.5-flash-image",
]

# --- ARGUMENTS ---
if len(sys.argv) < 3:
    print("Kullanım: ai.py <image_path> <prompt> [model1,model2,...]")
    sys.exit(1)

image_path = sys.argv[1]
prompt = sys.argv[2]

# --- MODELS FROM UI (OPTIONAL) ---
if len(sys.argv) >= 4 and sys.argv[3].strip():
    MODELS = [m.strip() for m in sys.argv[3].split(",")]
else:
    MODELS = DEFAULT_MODELS

# --- API KEY ---
API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not API_KEY:
    print("HATA: OPENROUTER_API_KEY not set")
    sys.exit(1)

# --- IMAGE LOAD ---
if not os.path.exists(image_path):
    print(f"HATA: Resim bulunamadı → {image_path}")
    sys.exit(1)

with open(image_path, "rb") as f:
    image_b64 = base64.b64encode(f.read()).decode("utf-8")

# --- REQUEST CONFIG ---
URL = "https://openrouter.ai/api/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "http://localhost",
    "X-Title": "ai-capture",
}

# --- MODEL TRY FUNCTION ---
def try_model(model_name):
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}"
                        }
                    }
                ],
            }
        ],
        "max_tokens": 512,
    }

    response = requests.post(
        URL,
        headers=HEADERS,
        json=payload,
        timeout=60,
    )

    if response.status_code == 200:
        data = response.json()
        return data["choices"][0]["message"]["content"]

    raise Exception(f"{model_name} → {response.status_code}: {response.text}")


# --- MAIN LOOP ---
for model in MODELS:
    try:
        answer = try_model(model)
        print(answer)
        sys.exit(0)
    except Exception as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        time.sleep(1)

print("HATA: Tüm modeller başarısız")
sys.exit(1)
