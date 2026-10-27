"""Flatten the BFS vote JSON files into tidy tables.

Output:
- data/processed/votes_long.parquet (one row per municipality per vote)
- data/processed/votes_national.parquet (one row per vote)
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "votes"
OUT_DIR = ROOT / "data" / "processed"


# pull out one title
def get_title(vorlage: dict, lang: str) -> str | None:
    """Return the vote title in one language ('en', 'fr', 'de', 'it', 'rm')."""
    for t in vorlage["vorlagenTitel"]:
        if t["langKey"] == lang:
            return t["text"]
    return None


# describe a vote
def vote_info(vorlage: dict, date: str) -> dict:
    """Columns that describe the vote itself (same for every municipality)."""
    return {
        "date": date,
        "vote_id": vorlage["vorlagenId"],
        "title_en": get_title(vorlage, "en"),
        "title_fr": get_title(vorlage, "fr"),
        "title_de": get_title(vorlage, "de"),
        "vote_type_id": vorlage.get("vorlagenArtId"),
        "main_vote_id": vorlage.get("hauptvorlagenId"),
        "accepted": vorlage.get("vorlageAngenommen"),
    }


# translate result fields
def result_columns(r: dict) -> dict:
    """Translate the German result fields into English column names."""
    return {
        "counted": r.get("gebietAusgezaehlt"),
        "electorate": r.get("anzahlStimmberechtigte"),
        "ballots_cast": r.get("eingelegteStimmzettel"),
        "valid_votes": r.get("gueltigeStimmen"),
        "yes_votes": r.get("jaStimmenAbsolut"),
        "no_votes": r.get("neinStimmenAbsolut"),
        "yes_pct": r.get("jaStimmenInProzent"),
        "turnout_pct": r.get("stimmbeteiligungInProzent"),
    }


# handle one file
def flatten_file(path: Path) -> tuple[list[dict], list[dict]]:
    """Read one voting Sunday's file, return (municipality rows, national rows)."""
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    date = data["abstimmtag"]
    muni_rows, national_rows = [], []

    for vorlage in data["schweiz"]["vorlagen"]:
        info = vote_info(vorlage, date)
        national_rows.append({**info, **result_columns(vorlage["resultat"])})

        for kanton in vorlage["kantone"]:
            for g in kanton.get("gemeinden", []):
                muni_rows.append({
                    **info,
                    "canton_nr": int(kanton["geoLevelnummer"]),
                    "canton": kanton["geoLevelname"],
                    "bfs_nr": int(g["geoLevelnummer"]),
                    "municipality": g["geoLevelname"],
                    **result_columns(g["resultat"]),
                })
    return muni_rows, national_rows


def main() -> None:
    files = sorted(RAW_DIR.glob("*.json"))
    print(f"Found {len(files)} files")

    all_muni, all_national = [], []
    for path in files:
        muni_rows, national_rows = flatten_file(path)
        all_muni.extend(muni_rows)
        all_national.extend(national_rows)

    df = pd.DataFrame(all_muni)
    national = pd.DataFrame(all_national)
    for frame in (df, national):
        frame["date"] = pd.to_datetime(frame["date"], format="%Y%m%d")

    # quick checks
    print(f"Municipality rows: {len(df):,}")
    print(f"Votes: {df['vote_id'].nunique()} on {df['date'].nunique()} dates")
    per_vote = df.groupby("vote_id")["bfs_nr"].nunique()
    print(f"Municipalities per vote: min {per_vote.min()}, max {per_vote.max()}")
    print(f"Duplicate (vote, municipality) pairs: {df.duplicated(['vote_id', 'bfs_nr']).sum()}")
    print("Missing values per column:")
    print(df.isna().sum()[lambda s: s > 0].to_string() or "  none")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_DIR / "votes_long.parquet", index=False)
    national.to_parquet(OUT_DIR / "votes_national.parquet", index=False)
    print(f"Saved to {OUT_DIR}")


if __name__ == "__main__":
    main()