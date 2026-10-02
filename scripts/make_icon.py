# Companion4SoloPlayer (C4SP) - Icon Creator script
from pathlib import Path

from PIL import Image

SRC = Path("./assets/icons/logo-512x512.png")
DST = Path("./assets/icons/icon.ico")

sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]

def generate_icon() -> None:
    img = Image.open(SRC)
    img.save(DST, format='ICO', sizes=sizes)
    print(f"[OK] {DST} generated.")

def main() -> None:
    # Si icon.ico n'existe pas → générer
    if not DST.exists():
        print(f"[INFO] {DST} does not exist → generating.")
        generate_icon()
        return

    # Vérifier les dates de modification
    src_mtime = SRC.stat().st_mtime
    dst_mtime = DST.stat().st_mtime

    if src_mtime > dst_mtime:
        print(f"[INFO] Source ICO is newer → regenerating {DST}.")
        generate_icon()
    else:
        print(f"[SKIP] {DST} is up to date → nothing to do.")

if __name__ == "__main__":
    main()

