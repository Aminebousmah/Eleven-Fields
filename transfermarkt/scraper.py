"""
Téléchargement du dataset Transfermarkt depuis Kaggle.

Source : https://www.kaggle.com/datasets/davidcariboo/player-scores
Mis à jour automatiquement chaque semaine (workflow GitHub Actions de
dcaribou/transfermarkt-datasets → publication Kaggle).

Pré-requis (deux méthodes — l'une OU l'autre) :

  Méthode A — variable d'environnement (nouveau format Kaggle, recommandé) :
    1. https://www.kaggle.com/settings/account → "Create New Token"
    2. Copier le token (commence par "KGAT_…")
    3. Définir KAGGLE_API_TOKEN dans l'environnement
       PowerShell : [Environment]::SetEnvironmentVariable('KAGGLE_API_TOKEN','KGAT_...','User')
       cmd        : setx KAGGLE_API_TOKEN "KGAT_..."

  Méthode B — fichier kaggle.json (ancien format, toujours supporté) :
    1. https://www.kaggle.com/settings/account → "Create New Token"
    2. Si le bouton télécharge un kaggle.json (username + key), le déposer dans
       C:\\Users\\<user>\\.kaggle\\kaggle.json

Usage :
    from transfermarkt.scraper import download
    download()                # télécharge dans transfermarkt_data/
    download(force=True)      # ré-écrase
"""
from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "transfermarkt_data"
KAGGLE_DATASET = "davidcariboo/player-scores"

# Fichiers attendus une fois unzipped
EXPECTED_CSVS = [
    "players.csv",
    "clubs.csv",
    "competitions.csv",
    "appearances.csv",
    "games.csv",
    "player_valuations.csv",
    "transfers.csv",
    "club_games.csv",
]


def _check_kaggle_creds() -> None:
    """
    Accepte :
      - KAGGLE_API_TOKEN (nouveau format, token unique commençant par KGAT_)
      - KAGGLE_USERNAME + KAGGLE_KEY (anciennes variables)
      - ~/.kaggle/kaggle.json (ancien fichier)
    """
    if os.environ.get("KAGGLE_API_TOKEN"):
        return
    if os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        return
    home = Path.home()
    cred = home / ".kaggle" / "kaggle.json"
    if cred.exists():
        return
    raise FileNotFoundError(
        "Aucun token Kaggle détecté. Définir KAGGLE_API_TOKEN :\n"
        "  PowerShell :  [Environment]::SetEnvironmentVariable('KAGGLE_API_TOKEN','KGAT_...','User')\n"
        "  cmd        :  setx KAGGLE_API_TOKEN \"KGAT_...\"\n"
        "Puis OUVRIR UN NOUVEAU TERMINAL avant de relancer."
    )


def download(force: bool = False) -> Path:
    """Télécharge & dézippe le dataset Kaggle dans `transfermarkt_data/`."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not force and all((DATA_DIR / f).exists() for f in EXPECTED_CSVS):
        print(f"✓ Dataset déjà présent dans {DATA_DIR}/ (force=True pour re-télécharger)")
        return DATA_DIR

    _check_kaggle_creds()

    # Import retardé : la lib lit kaggle.json au moment de l'import
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()

    print(f"📥 Téléchargement de {KAGGLE_DATASET}…")
    api.dataset_download_files(KAGGLE_DATASET, path=str(DATA_DIR), unzip=True, quiet=False)

    print(f"✓ Décompressé dans {DATA_DIR}/")
    for f in EXPECTED_CSVS:
        path = DATA_DIR / f
        if path.exists():
            size_mb = path.stat().st_size / 1e6
            print(f"  - {f}  ({size_mb:.1f} MB)")
        else:
            print(f"  ⚠ manquant : {f}")

    return DATA_DIR


if __name__ == "__main__":
    download()
