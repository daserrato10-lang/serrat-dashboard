"""
Genera imágenes con Imagen 4.0 y Gemini para carruseles de Serrat Relojes.
Filosofía: Director de Arte editorial — analógico, cinematográfico, metafórico.
NUNCA generar relojes directamente — solo texturas, atmósferas, personas.
Para relojes: usar gemini-3.1-flash-image con foto DSC como referencia.
Uso: python3 execution/generate_images.py
Salida: .tmp/ai_images/
"""

import os, base64, requests
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

API_KEY  = os.getenv("GEMINI_API_KEY")
OUT_DIR  = Path(".tmp/ai_images")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def imagen(name, prompt, ratio="3:4"):
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict?key={API_KEY}",
        json={"instances":[{"prompt":prompt}],"parameters":{"sampleCount":1,"aspectRatio":ratio,"outputOptions":{"mimeType":"image/jpeg","compressionQuality":95}}},
        timeout=120
    )
    r.raise_for_status()
    b64 = r.json()["predictions"][0]["bytesBase64Encoded"]
    p = OUT_DIR / f"{name}.jpg"
    p.write_bytes(base64.b64decode(b64))
    print(f"  ✓ {name}")
    return p

def gemini_ref(name, ref_path, prompt):
    with open(ref_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image:generateContent?key={API_KEY}",
        json={"contents":[{"parts":[{"text":prompt},{"inline_data":{"mime_type":"image/jpeg","data":img_b64}}]}],"generationConfig":{"responseModalities":["IMAGE","TEXT"]}},
        timeout=120
    )
    part = r.json()["candidates"][0]["content"]["parts"][0]
    p = OUT_DIR / f"{name}.jpg"
    p.write_bytes(base64.b64decode(part["inlineData"]["data"]))
    print(f"  ✓ {name}")
    return p

JOBS = [
    ("imagen", "prima_s1_cover",
     "Extreme macro close-up of a stack of worn Colombian peso banknotes resting on a surface of deep brushed dark steel. "
     "A single narrow beam of warm amber theatrical light from the upper left grazes across the paper surface, "
     "revealing the deep tactile texture of the cotton-linen paper — fibers, micro-engravings, subtle color gradients. "
     "Bills slightly out of focus at edges, crisp at center. Deep black shadows fill negative space. "
     "The mood is serious, deliberate, about weight and value. "
     "Pervasive granular 35mm film grain. Moody cinematic lighting. No text, no faces, no logos. Analog camera aesthetic."),

    ("imagen", "prima_s2_efimero",
     "Editorial still life: a crumpled discarded receipt and torn paper bag scattered on cold dark concrete. "
     "Shot from directly above. A single shaft of cool blue-grey light picks out the texture of concrete and paper. "
     "The paper is wrinkled and spent — something used and thrown away. Empty, fast, forgettable. "
     "Pervasive granular film grain, deep tactile textures, moody directional lighting. "
     "No text, no logos, only grey concrete and shadow. Large format analog camera aesthetic."),

    ("imagen", "prima_s5_cierre",
     "Editorial portrait: a Latin American man in his early 30s, mid-torso up. "
     "Dark charcoal merino turtleneck. Easy confident posture — someone at rest after a good decision. "
     "Gazes slightly downward, quiet self-satisfied expression. "
     "Background: softly blurred warm interior — dark wood paneling, amber light from a window. "
     "Light falls from the right, left side in cinematic shadow. "
     "Pervasive granular 35mm film grain, muted warm tones, deep blacks. "
     "Editorial analog photography. No watch visible. No accessories. No text."),
]

if __name__ == "__main__":
    print(f"Generando {len(JOBS)} imágenes...\n")
    for job in JOBS:
        try:
            if job[0] == "imagen":
                imagen(job[1], job[2])
            else:
                gemini_ref(job[1], job[2], job[3])
        except Exception as e:
            print(f"  ✗ {job[1]}: {e}")
    print("\nListo.")
