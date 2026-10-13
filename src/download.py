"""Download federal vote results from the Swiss Federal Statistical Office (BFS).

One JSON file per voting Sunday, with results for every municipality.
"""
from pathlib import Path
import requests

BASE_URL = "https://ogd-static.voteinfo-app.ch/v1/ogd/sd-t-17-02-20140209-eidgAbstimmung.json"

# data/raw/votes/, found relative to this file so it works from any folder
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "votes"

def download_vote(date: str, overwrite: bool=False) -> Path:
    """Download one voting Sunday. `date` is 'YYYYMMDD', e.g. '20140209'."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DIR / f"{date}.json"
    
    if out_path.exists() and not overwrite:
        print(f"Already have {out_path.name}, skipping")
        return out_path
    
    url = BASE_URL.format(date=date)
    response = requests.get(url, timeout=60)
    response.raise_for_status() # stops with an error if download failed
    
    out_path.write_bytes(response.content)
    size_mb = len(response.content) / 1_000_000
    print(f"Saved {out_path.name} ({size_mb:.1f} MB)")
    return out_path

if __name__ == "__main__":
    download_vote("20140209")