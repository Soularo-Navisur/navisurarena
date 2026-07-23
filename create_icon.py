"""
create_icon.py — Génère navisur.ico depuis navisur_logo.jpg
Lancer une seule fois avant de builder l'exe.
"""
import struct
import io
import os
import sys

def create_ico():
    try:
        from PIL import Image
    except ImportError:
        print("Installation de Pillow...")
        os.system(f'"{sys.executable}" -m pip install pillow')
        from PIL import Image

    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'navisur_logo.jpg')
    if not os.path.exists(logo_path):
        print(f"ERREUR : navisur_logo.jpg introuvable dans {os.path.dirname(logo_path)}")
        input("Appuyez sur Entrée pour quitter...")
        sys.exit(1)

    print("Chargement du logo...")
    logo = Image.open(logo_path).convert('RGBA')

    sizes = [16, 32, 48, 64, 128, 256]
    print(f"Génération des résolutions : {sizes}")

    # Encoder chaque taille en PNG
    png_data = []
    for s in sizes:
        img = logo.resize((s, s), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        png_data.append(buf.getvalue())

    # Construire le fichier ICO multi-résolution
    num_images = len(sizes)
    header = struct.pack('<HHH', 0, 1, num_images)
    header_size = 6 + num_images * 16

    offsets = []
    offset = header_size
    for data in png_data:
        offsets.append(offset)
        offset += len(data)

    entries = b''
    for i, s in enumerate(sizes):
        w = 0 if s == 256 else s
        h = 0 if s == 256 else s
        entries += struct.pack('<BBBBHHII', w, h, 0, 0, 1, 32,
                               len(png_data[i]), offsets[i])

    ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'navisur.ico')
    with open(ico_path, 'wb') as f:
        f.write(header + entries + b''.join(png_data))

    print(f"✅ navisur.ico créé : {os.path.getsize(ico_path):,} bytes")

    # Aussi PNG 256x256 pour le splash screen
    png_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'navisur_256.png')
    logo.resize((256, 256), Image.LANCZOS).save(png_path)
    print(f"✅ navisur_256.png créé")

    print("\nFichiers prêts pour la compilation !")

if __name__ == '__main__':
    create_ico()
    input("\nAppuyez sur Entrée pour fermer...")
