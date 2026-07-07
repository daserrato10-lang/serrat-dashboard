"""
Exporta un carrusel o historia HTML a imágenes PNG listas para Instagram.
Formatos soportados:
  - Carrusel 4:5  → 1080×1350px  (viewer 480×600px)   [default]
  - Historia 9:16 → 1080×1920px  (viewer 405×720px)   [--story]
Uso:
  python3 execution/export_carousel.py .tmp/carousel.html
  python3 execution/export_carousel.py .tmp/historia.html --story
Salida: .tmp/export/<nombre>/slide_01.png … slide_N.png

Validación automática de overflow:
  Antes de exportar cada slide, verifica que ningún elemento de texto
  se salga del viewer. Si hay overflow, lo reporta con ⚠️ y el texto afectado.
"""

import sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

FORMATS = {
    "carousel": {"export_w": 1080, "export_h": 1350, "viewer_w": 480, "viewer_h": 600},
    "story":    {"export_w": 1080, "export_h": 1920, "viewer_w": 405, "viewer_h": 720},
}

OVERFLOW_CHECK_JS = """
() => {
    const viewer = document.querySelector('.viewer');
    const viewerRect = viewer.getBoundingClientRect();
    const problems = [];

    // Revisar todos los elementos de texto dentro del slide activo
    const activeSlide = viewer.querySelector('.slide.active');
    if (!activeSlide) return problems;

    const textEls = activeSlide.querySelectorAll('div, span, p');
    textEls.forEach(el => {
        const rect = el.getBoundingClientRect();
        const text = el.innerText ? el.innerText.trim() : '';
        if (!text || text.length < 2) return;

        // Detectar si el elemento se sale por la derecha del viewer
        const rightEdge = viewerRect.right;
        if (rect.right > rightEdge + 2) {
            const overflow = Math.round(rect.right - rightEdge);
            const style = window.getComputedStyle(el);
            problems.push({
                text: text.substring(0, 60),
                overflow_px: overflow,
                font_size: style.fontSize,
                font_weight: style.fontWeight
            });
        }

        // Detectar si el propio elemento tiene scroll horizontal (texto cortado)
        if (el.scrollWidth > el.clientWidth + 2) {
            const overflow = el.scrollWidth - el.clientWidth;
            const style = window.getComputedStyle(el);
            const entry = {
                text: text.substring(0, 60),
                overflow_px: overflow,
                font_size: style.fontSize,
                font_weight: style.fontWeight
            };
            // Evitar duplicados
            if (!problems.find(p => p.text === entry.text)) {
                problems.push(entry);
            }
        }
    });
    return problems;
}
"""

def export(html_path: str, fmt: str = "carousel"):
    html_file = Path(html_path).resolve()
    if not html_file.exists():
        sys.exit(f"No encontré: {html_file}")

    f = FORMATS[fmt]
    VIEWER_W, VIEWER_H = f["viewer_w"], f["viewer_h"]
    SCALE = f["export_w"] / VIEWER_W

    out_dir = html_file.parent.parent / ".tmp" / "export" / html_file.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    url = html_file.as_uri()
    overflow_found = False

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(
            viewport={"width": VIEWER_W + 200, "height": VIEWER_H + 200},
            device_scale_factor=SCALE,
        )
        page.goto(url, wait_until="networkidle")
        time.sleep(1)  # esperar fuentes

        n = page.locator(".slide").count()
        print(f"Slides detectados: {n}")

        for i in range(n):
            # Activar slide i
            page.evaluate(f"""() => {{
                document.querySelectorAll('.slide').forEach((s,idx) => {{
                    s.classList.toggle('active', idx === {i});
                }});
                document.querySelectorAll('.dot').forEach((d,idx) => {{
                    d.classList.toggle('active', idx === {i});
                }});
            }}""")
            time.sleep(0.2)

            # Validar overflow ANTES de exportar
            problems = page.evaluate(OVERFLOW_CHECK_JS)
            if problems:
                overflow_found = True
                print(f"\n  ⚠️  OVERFLOW en slide_{i+1:02d}:")
                for p in problems:
                    print(f"     → \"{p['text']}\"  |  font-size: {p['font_size']}  |  se sale {p['overflow_px']}px")

            viewer = page.locator(".viewer")
            out = out_dir / f"slide_{i+1:02d}.png"
            viewer.screenshot(path=str(out))
            status = "⚠️ " if problems else "✓ "
            print(f"  {status}slide_{i+1:02d}.png")

        browser.close()

    print(f"\nExportados en: {out_dir}")
    if overflow_found:
        print("\n⚠️  HAY SLIDES CON TEXTO CORTADO — revisa los avisos arriba y corrige los font-sizes antes de publicar.")
    else:
        print("✓  Sin overflow detectado. Todos los textos caben correctamente.")
    return out_dir

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Uso: python3 execution/export_carousel.py <ruta.html> [--story]")
    fmt = "story" if "--story" in sys.argv else "carousel"
    export(sys.argv[1], fmt)
