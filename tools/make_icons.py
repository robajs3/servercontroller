"""Generuje ikony PWA do app/static/pwa/ (wymaga Pillow: pip install pillow).
Uruchom z katalogu głównego repo: python tools/make_icons.py"""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "app" / "static" / "pwa"
BG, PANEL, EDGE, GREEN, BLUE = "#0f1115", "#232833", "#3b4252", "#22c55e", "#3b82f6"
S = 1024   # rysujemy dużo większe i skalujemy w dół (wygładzenie)

def draw(content=0.62, rounded=False, mono=False):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if not mono:
        d.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22) if rounded else 0, fill=BG)
    w = S * content; x0 = (S - w) / 2; h = w * 0.27; gap = w * 0.07; y = (S - (3 * h + 2 * gap)) / 2
    for i in range(3):
        top = y + i * (h + gap)
        if mono:
            d.rounded_rectangle([x0, top, x0 + w, top + h], radius=h * 0.2, fill="white")
            d.ellipse([x0 + w - h * 0.75, top + h * 0.25, x0 + w - h * 0.25, top + h * 0.75], fill=(0, 0, 0, 0))  # dioda = dziura (alfa 0)
        else:
            d.rounded_rectangle([x0, top, x0 + w, top + h], radius=h * 0.2, fill=PANEL, outline=EDGE, width=int(S * 0.006))
            d.ellipse([x0 + w - h * 0.78, top + h * 0.22, x0 + w - h * 0.22, top + h * 0.78], fill=GREEN if i != 1 else BLUE)
            d.rounded_rectangle([x0 + h * 0.3, top + h * 0.38, x0 + w * 0.45, top + h * 0.62], radius=h * 0.12, fill=EDGE)
    return img

def save(img, name, size):
    OUT.mkdir(parents=True, exist_ok=True)
    img.resize((size, size), Image.LANCZOS).save(OUT / name, optimize=True)

save(draw(rounded=True), "icon-192.png", 192)
save(draw(rounded=True), "icon-512.png", 512)
save(draw(content=0.5), "icon-maskable-512.png", 512)     # pełne tło, treść w bezpiecznej strefie (80%)
save(draw(content=0.6), "apple-touch-icon.png", 180)      # iOS sam zaokrągla rogi
save(draw(content=0.8, mono=True), "badge-96.png", 96)    # biała sylwetka na przezroczystym tle (pasek stanu Androida)
print("OK:", sorted(p.name for p in OUT.iterdir()))
