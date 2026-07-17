from __future__ import annotations

from pathlib import Path
import shutil


def main() -> int:
    dashboard_root = Path(__file__).resolve().parent
    src_dir = dashboard_root.parent / "P13" / "Partie_1" / "P6_ameliore_IA" / "notebooks" / "output"
    dst_dir = dashboard_root / "data"
    dst_dir.mkdir(parents=True, exist_ok=True)

    files_to_sync = [
        "bc05_matrice_decisionnelle.csv",
        "bc05_matrice_critique_surveillance.csv",
        "bc05_alertes_actionnables.csv",
        "bc05_anomalies_summary.csv",
        "bc05_iforest_alerts.csv",
    ]

    print(f"Source: {src_dir}")
    print(f"Cible : {dst_dir}")

    if not src_dir.exists():
        print("ERREUR: dossier source introuvable.")
        return 1

    copied = 0
    missing = []

    for filename in files_to_sync:
        src_file = src_dir / filename
        dst_file = dst_dir / filename
        if src_file.exists():
            shutil.copy2(src_file, dst_file)
            copied += 1
            print(f"OK   {filename}")
        else:
            missing.append(filename)
            print(f"MISS {filename}")

    print("-" * 50)
    print(f"Copies: {copied}/{len(files_to_sync)}")

    if missing:
        print("Fichiers manquants (a regenerer dans le notebook):")
        for m in missing:
            print(f"- {m}")

    return 0 if copied > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
