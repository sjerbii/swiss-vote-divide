# swiss-vote-divide
Measuring how much Switzerland’s language divide (the “Röstigraben”) affects referendum results across ~2,100 municipalities, beyond demographics. Python, GeoPandas, statsmodels, Streamlit.

## Project Log
### 1 - Setup and first look at data (10/13)

**Done**
- Set up repo, virtual environment and `requirements.txt` (requests, pandas, ipykernel)
- Wrote `src/download.py`, which downloads one voting Sunday's results from the Federal Statistical Office (BFS) and skips files that are already downloaded
- Explored the 9 February 2014 file in `notebooks/00_explore_json.ipynb`

**Main Takeaways**
- Each voting Sunday is one JSON file. Municipality results sit at `schweiz -> vorlagen -> kantone -> gemeinden -> resultat`
- Every municipality has a BFS number (`geoLevelnummer`), which will be the key for joining language region, demographics, and map boundaries
- Older votes are already mapped to the 2026 municipality list, so municipality mergers won't need to be fixed manually
- Feb 9th 2014 had 3 votes: the mass immigration initiative got 50.3% yes nationally, and the lowest yes-shares were mostly in cantons Vaud, Fribourg, and Jura.

**Next**
- Download every voting Sunday from 2010 to 2025
- Flatten all votes into one table and save it as Parquet