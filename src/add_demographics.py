"""Add 2017 demographics for each municipality to the vote results.

Variables:
- urban_rural: BFS urban/rural typology (STALAN2020), already on 2026 numbers
- share_65plus: share of permanent residents aged 65+ (BFS STATPOP, 2017)
- avg_income: average net income per taxpayer in Fr. (ESTV direct federal tax, 2017)

Older municipality numbers are converted to the 2026 list with the BFS
correspondence table. Merged municipalities are combined by summing counts
and totals first, then dividing (a weighted average).

Output:
- data/processed/votes_demographics.parquet (votes_language plus the three columns)
"""

import warnings
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
MUNICIPALITIES_PATH = RAW_DIR / "municipalities_2026.csv"  # from add_language.py
VOTES_PATH = ROOT / "data" / "processed" / "votes_language.parquet"
OUT_PATH = ROOT / "data" / "processed" / "votes_demographics.parquet"

YEAR = "2017"

INCOME_URL = (
    "https://www.estv.admin.ch/dam/de/sd-web/utk8kIXUHW5g/"
    "statistik-dbst-np-gemeinde-2017-auswertung-de.xlsx"
)
INCOME_PATH = RAW_DIR / "income_2017.xlsx"
# taxpayers with and without federal tax, workers and retirees: together everyone
INCOME_SHEETS = ["211", "212", "311", "312"]

AGE_URL = "https://www.pxweb.bfs.admin.ch/api/v1/de/px-x-0102010000_101/px-x-0102010000_101.px"
AGE_PATH = RAW_DIR / "age_2017.csv"
GEO_VAR = "Kanton (-) / Bezirk (>>) / Gemeinde (......)"

MAPPING_URL = (
    "https://www.agvchapp.bfs.admin.ch/api/communes/correspondances"
    "?startPeriod=01-01-{start}&endPeriod=01-01-2026"
)
# the ESTV file uses the municipality list of 1 Jan 2017,
# the age table uses the 2025 list for every year
INCOME_LIST_YEAR = "2017"
AGE_LIST_YEAR = "2025"

URBAN_RURAL = {1: "urban", 2: "intermediate", 3: "rural"}


# download helper
def download(url: str, path: Path, json_query: dict | None = None) -> Path:
    """Download url to path (POST if json_query is given), unless we already have it."""
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        print(f"Already have {path.name}, skipping")
        return path

    if json_query is None:
        response = requests.get(url, timeout=120)
    else:
        response = requests.post(url, json=json_query, timeout=120)
    response.raise_for_status()  # stops with an error if download failed

    path.write_bytes(response.content)
    print(f"Saved {path.name}")
    return path


# old number -> 2026 number
def load_mapping(list_year: str) -> pd.DataFrame:
    """BFS table of municipalities that changed between 1 Jan `list_year` and 1 Jan 2026."""
    path = download(MAPPING_URL.format(start=list_year), RAW_DIR / f"municipality_changes_{list_year}_2026.csv")
    mapping = pd.read_csv(path)[["InitialCode", "TerminalCode"]]
    return mapping.rename(columns={"InitialCode": "old_bfs_nr", "TerminalCode": "bfs_nr"})


def to_2026(table: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    """Replace old_bfs_nr with the 2026 bfs_nr. Numbers not in the mapping keep their value."""
    table = table.merge(mapping, on="old_bfs_nr", how="left")
    changed = table["bfs_nr"].notna() & (table["bfs_nr"] != table["old_bfs_nr"])
    print(f"  {table.loc[changed, 'old_bfs_nr'].nunique()} old numbers mapped to a new number")
    table["bfs_nr"] = table["bfs_nr"].fillna(table["old_bfs_nr"]).astype(int)
    return table.drop(columns="old_bfs_nr")


# urban / rural
def load_urban_rural() -> pd.DataFrame:
    raw = pd.read_csv(MUNICIPALITIES_PATH)
    table = raw[["BfsCode", "STALAN2020"]].rename(columns={"BfsCode": "bfs_nr"})
    table["urban_rural"] = table["STALAN2020"].map(URBAN_RURAL)
    if table["urban_rural"].isna().any():
        raise ValueError("Unknown urban/rural codes in BFS table")
    return table[["bfs_nr", "urban_rural"]]


# share over 65
def age_query(municipality_codes: list[str]) -> dict:
    """PX-Web query: 2017 permanent residents, total plus each age from 65 up."""
    ages = ["-99999"] + [str(a) for a in range(65, 101)]  # -99999 is the total
    return {
        "query": [
            {"code": "Jahr", "selection": {"filter": "item", "values": [YEAR]}},
            {"code": GEO_VAR, "selection": {"filter": "item", "values": municipality_codes}},
            {"code": "Bevölkerungstyp", "selection": {"filter": "item", "values": ["1"]}},
            {"code": "Staatsangehörigkeit (Kategorie)", "selection": {"filter": "item", "values": ["-99999"]}},
            {"code": "Geschlecht", "selection": {"filter": "item", "values": ["-99999"]}},
            {"code": "Alter", "selection": {"filter": "item", "values": ages}},
        ],
        "response": {"format": "csv"},
    }


def load_age() -> pd.DataFrame:
    if not AGE_PATH.exists():
        # municipalities are the geo entries labelled "......<4-digit number> <name>"
        meta = requests.get(AGE_URL, timeout=60).json()
        geo = next(v for v in meta["variables"] if v["code"] == GEO_VAR)
        codes = [code for code, text in zip(geo["values"], geo["valueTexts"]) if text.startswith("......")]
        download(AGE_URL, AGE_PATH, json_query=age_query(codes))

    raw = pd.read_csv(AGE_PATH, encoding="cp1252")
    age_cols = [c for c in raw.columns if c.endswith("Jahre") or c.endswith("mehr")]
    table = pd.DataFrame({
        "old_bfs_nr": raw[GEO_VAR].str.extract(r"(\d{4})")[0].astype(int),
        "population": raw["Alter - Total"],
        "pop_65plus": raw[age_cols].sum(axis=1),
    })

    print("Age:")
    table = to_2026(table, load_mapping(AGE_LIST_YEAR))
    table = table.groupby("bfs_nr", as_index=False)[["population", "pop_65plus"]].sum()
    table["share_65plus"] = table["pop_65plus"] / table["population"]
    return table[["bfs_nr", "share_65plus"]]


# average income
def read_income_sheet(path: Path, sheet: str) -> pd.DataFrame:
    """Taxpayers and net income (in Fr.) per municipality from one ESTV sheet."""
    with warnings.catch_warnings():
        # the ESTV workbook has print settings openpyxl can't read; harmless
        warnings.simplefilter("ignore", UserWarning)
        raw = pd.read_excel(path, sheet_name=sheet, header=None, skiprows=13)
    rows = raw[pd.to_numeric(raw[1], errors="coerce").notna()]  # municipality rows only
    return pd.DataFrame({
        "old_bfs_nr": rows[1].astype(int),
        # "*" means hidden for privacy -> NaN
        "taxpayers": pd.to_numeric(rows[5], errors="coerce"),
        "net_income": pd.to_numeric(rows[13], errors="coerce") * 1000,
    })


def load_income() -> pd.DataFrame:
    path = download(INCOME_URL, INCOME_PATH)
    sheets = pd.concat([read_income_sheet(path, s) for s in INCOME_SHEETS])

    print("Income:")
    table = to_2026(sheets, load_mapping(INCOME_LIST_YEAR))
    # min_count=len keeps a NaN if any part is missing, so a hidden count empties the total
    table = table.groupby("bfs_nr").agg(
        taxpayers=("taxpayers", lambda s: s.sum(min_count=len(s))),
        net_income=("net_income", lambda s: s.sum(min_count=len(s))),
    ).reset_index()
    table["avg_income"] = table["net_income"] / table["taxpayers"]
    print(f"  {table['avg_income'].isna().sum()} municipalities with empty income (hidden counts)")
    return table[["bfs_nr", "avg_income"]]


# join and check
def add_demographics(votes: pd.DataFrame, demographics: pd.DataFrame) -> pd.DataFrame:
    """Merge on bfs_nr. Error if a vote municipality has no demographics row."""
    merged = votes.merge(demographics, on="bfs_nr", how="left", indicator=True)

    unmatched = merged.loc[merged["_merge"] == "left_only", "bfs_nr"].unique().tolist()
    if unmatched:
        raise ValueError(f"No demographics for bfs_nr: {sorted(unmatched)}")

    return merged.drop(columns="_merge")


if __name__ == "__main__":
    urban_rural = load_urban_rural()
    age = load_age()
    income = load_income()

    # inner joins: a municipality must be in all three tables to get a row
    demographics = urban_rural.merge(age, on="bfs_nr").merge(income, on="bfs_nr")

    votes = pd.read_parquet(VOTES_PATH)
    result = add_demographics(votes, demographics)
    result.to_parquet(OUT_PATH, index=False)

    per_muni = result.drop_duplicates("bfs_nr")
    print("\nMunicipality averages by language:")
    print(per_muni.groupby("language")[["share_65plus", "avg_income"]].mean().round(3).to_string())
    print("\nUrban/rural by language (municipalities):")
    print(pd.crosstab(per_muni["language"], per_muni["urban_rural"]).to_string())
    print(f"\nSaved {OUT_PATH.name} ({len(result)} rows)")
