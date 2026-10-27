"""Add each municipality's language region to the vote results.

Language regions come from the BFS municipality classifications
(column SPRGEB2020) for the 2026 municipality list, which is the list
the vote data is already mapped to.

Output:
- data/processed/votes_language.parquet (votes_long plus a `language` column)
"""

from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
LOOKUP_URL = "https://www.agvchapp.bfs.admin.ch/api/communes/levels?date=01-01-2026"
LOOKUP_PATH = ROOT / "data" / "raw" / "municipalities_2026.csv"
VOTES_PATH = ROOT / "data" / "processed" / "votes_long.parquet"
OUT_PATH = ROOT / "data" / "processed" / "votes_language.parquet"

# BFS language region codes
LANGUAGE_CODES = {1: "de", 2: "fr", 3: "it", 4: "rm"}

# Swiss abroad units use bfs_nr 9000 and up, real municipalities are below
ABROAD_MIN_BFS = 9000


# get the BFS table
def download_lookup(overwrite: bool = False) -> Path:
    """Download the 2026 municipality classifications CSV, unless we already have it."""
    LOOKUP_PATH.parent.mkdir(parents=True, exist_ok=True)

    if LOOKUP_PATH.exists() and not overwrite:
        print(f"Already have {LOOKUP_PATH.name}, skipping")
        return LOOKUP_PATH

    response = requests.get(LOOKUP_URL, timeout=60)
    response.raise_for_status()  # stops with an error if download failed

    LOOKUP_PATH.write_bytes(response.content)
    print(f"Saved {LOOKUP_PATH.name}")
    return LOOKUP_PATH


# build (bfs_nr, language)
def load_lookup(path: Path) -> pd.DataFrame:
    """Return one row per municipality with columns bfs_nr and language."""
    raw = pd.read_csv(path)
    lookup = raw[["BfsCode", "SPRGEB2020"]].rename(
        columns={"BfsCode": "bfs_nr", "SPRGEB2020": "code"}
    )

    unknown = set(lookup["code"]) - set(LANGUAGE_CODES)
    if unknown:
        raise ValueError(f"Unknown language codes in BFS table: {sorted(unknown)}")
    if lookup["bfs_nr"].duplicated().any():
        raise ValueError("BFS table has duplicate bfs_nr values")

    lookup["language"] = lookup["code"].map(LANGUAGE_CODES)
    return lookup[["bfs_nr", "language"]]


# join and check
def add_language(votes: pd.DataFrame, lookup: pd.DataFrame) -> pd.DataFrame:
    """Drop Swiss abroad units, then merge on bfs_nr. Error if anything is left unmatched."""
    abroad = votes["bfs_nr"] >= ABROAD_MIN_BFS
    print(f"Dropping {abroad.sum()} abroad rows ({votes.loc[abroad, 'bfs_nr'].nunique()} units)")
    votes = votes[~abroad]

    merged = votes.merge(lookup, on="bfs_nr", how="left", indicator=True)

    unmatched = merged.loc[merged["_merge"] == "left_only", "bfs_nr"].unique().tolist()
    if unmatched:
        raise ValueError(f"No language for bfs_nr: {sorted(unmatched)}")

    return merged.drop(columns="_merge")


if __name__ == "__main__":
    lookup = load_lookup(download_lookup())
    votes = pd.read_parquet(VOTES_PATH)

    result = add_language(votes, lookup)
    result.to_parquet(OUT_PATH, index=False)

    print(f"\nRows per language:\n{result['language'].value_counts().to_string()}")
    print(f"\nSaved {OUT_PATH.name} ({len(result)} rows)")
