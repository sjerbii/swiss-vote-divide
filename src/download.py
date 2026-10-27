"""Download federal vote results from the Swiss Federal Statistical Office (BFS).

One JSON file per voting Sunday, with results for every municipality.
"""
from pathlib import Path
import time
import requests

BASE_URL = "https://ogd-static.voteinfo-app.ch/v1/ogd/sd-t-17-02-{date}-eidgAbstimmung.json"

VOTE_DATES = [
    "20100307", "20100926", "20101128", "20110213", "20120311", "20120617", "20120923", "20121125", 
    "20130303", "20130609", "20130922", "20131124","20140209", "20140518", "20140928", "20141130",
    "20150308", "20150614", "20160228", "20160605", "20160925", "20161127","20170212", "20170521", 
    "20170924", "20180304", "20180610", "20180923", "20181125", "20190210", "20190519", "20200209", 
    "20200927", "20201129", "20210307", "20210613", "20210926", "20211128", "20220213", "20220515", 
    "20220925", "20230618", "20240303", "20240609", "20240922", "20241124", "20250209", "20250928", 
    "20251130",
]

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

    
def download_all(dates=VOTE_DATES, pause: float=1.0) -> list[str]:
    """Download every date in list. Returns dates that failed."""
    failed = []
    for i, date in enumerate(dates, start=1):
        print(f"[{i}/{len(dates)}] ", end="")
        already_had = (RAW_DIR / f"{date}.json").exists()
        try:
            download_vote(date)
        except requests.RequestException as error:
            print(f"Failed {date}: {error}")
            failed.append(date)
            continue
        if not already_had:
            time.sleep(pause)
    print(f"\nDone: {len(dates) - len(failed)} succeeded, {len(failed)} failed {failed}")
    return failed

if __name__ == "__main__":
    download_all()