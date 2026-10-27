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
  - Exception (found later): Jaberg (868) only appears from March 2018 and Rüti bei Lyssach (422) from March 2021. Before that their votes look like they were counted with Kirchdorf (BE) and Hindelbank. Left as is since the effect is tiny
- Feb 9th 2014 had 3 votes: the mass immigration initiative got 50.3% yes nationally, and the lowest yes-shares were mostly in cantons Vaud, Fribourg, and Jura.

**Next**
- Download every voting Sunday from 2010 to 2025
- Flatten all votes into one table and save it as Parquet

### 2 - Full dataset and language regions (10/26)

**Done**
- Extended `src/download.py` to download all 49 voting Sundays from 2010 to 2025, with a short pause between downloads
- Wrote `src/clean_votes.py`, which flattens the JSON into `votes_long.parquet` (one row per municipality per vote) and `votes_national.parquet` (one row per vote), with English column names
- Checked the combined data in `notebooks/01_check_votes.ipynb`
- Wrote `src/add_language.py`, which adds each municipality's language region from the BFS 2026 municipality classifications and saves `votes_language.parquet`

**Main Takeaways**
- 136 federal votes across 49 voting Sundays. `main_vote_id` is always empty, so vote types come from `vote_type_id`
- Some cantons report Swiss citizens living abroad as separate units with BFS numbers of 9000 and up (12 in total). They aren't places, so they're dropped before the language join
- The language join checks itself: any vote row without a language makes the script stop instead of losing rows silently. All 2,105 municipalities matched
- The BFS gives each municipality one language region (de 1,369 · fr 606 · it 115 · rm 15), so bilingual places like Biel/Bienne get a single label

**Next**
- Find a source for municipality demographics and join it the same way

### 3 - Demographics (10/27)

**Done**
- Wrote `src/add_demographics.py`, which adds three 2017 variables to each municipality and saves `votes_demographics.parquet`:
  - `urban_rural`: the BFS urban/rural typology (urban, intermediate, rural)
  - `share_65plus`: share of residents aged 65 and over (BFS population statistics)
  - `avg_income`: average net income per taxpayer (Federal Tax Administration, all taxpayers with and without federal tax)

**Main Takeaways**
- One snapshot year (2017, the middle of the vote period) instead of a value per vote year. Age and income change slowly, so this keeps things simple
- 2017 data uses 2017 municipality numbers. A BFS list of old → new numbers converts them to the 2026 list (179 numbers changed). Merged municipalities are combined with weighted averages: add up the counts and totals, then divide
- Used average instead of median income because medians can't be combined when municipalities merge. The downside is outliers: Vaux-sur-Morges has an average of 578,660 Fr.
- The tax office hides taxpayer counts in tiny municipalities for privacy. Those get an empty income (19 municipalities), including merged ones where one part was hidden
- First look: Italian- and Romansh-speaking municipalities are older and poorer on average, French-speaking ones slightly richer than German-speaking ones. So these variables are worth controlling for

**Next**
- Explore the joined data and decide how to model the language effect