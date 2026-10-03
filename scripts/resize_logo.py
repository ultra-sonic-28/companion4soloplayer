# Companion4SoloPlayer (C4SP) - Logo Resizer script
# scripts/resize_logo.py
from pathlib import Path

from PIL import Image

SRC = Path("./assets/icons/logo-512x512.png")
DST = Path("./docs/assets/logo-64x64.png")
size = (64, 64)

def generate_logo() -> None:
    img = Image.open(SRC)
    img = img.resize(size)
    img.save(DST, format='PNG')
    print(f"[OK] {DST} generated.")

def main():

    if not DST.exists():
        print(f"[INFO] {DST} does not exist → generating.")
        generate_logo()
        return

    # Vérifier les dates de modification
    src_mtime = SRC.stat().st_mtime
    dst_mtime = DST.stat().st_mtime

    if src_mtime > dst_mtime:
        print(f"[INFO] Source PNG is newer → regenerating {DST}.")
        generate_logo()
    else:
        print(f"[SKIP] {DST} is up to date → nothing to do.")

if __name__ == "__main__":
    main()

