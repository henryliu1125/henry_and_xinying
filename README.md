# Chicago Crime Patterns and Socioeconomic Correlates
Group 42 — Xinying Jiang & Henry Liu

## Streamlit App
Access the interactive dashboard here:
[https://henryandxinying-t4ojwtdhvmqnjkozmh5jne.streamlit.app](https://henryandxinying-t4ojwtdhvmqnjkozmh5jne.streamlit.app)

> **Note:** Streamlit apps need to be "woken up" if they have not been run in the last 24 hours. If you see a sleeping screen, click "Wake up" and wait ~30 seconds.

## Setup
```bash
pip install -r requirements.txt
```

## Data Sources
- **Crime data**: Downloaded from the [Chicago Data Portal](https://data.cityofchicago.org/Public-Safety/Crimes-2001-to-Present/ijzp-q8t2), with a date filter applied on the portal (Date: 01/01/2024 – 12/31/2024) prior to download, yielding a 2024-only subset stored at data/Crimes_-_2001_to_Present_20260304.csv.
- **ACS data**: Downloaded from [Census ACS 5-Year Estimates 2024](https://data.census.gov) (tables B15003, S2301, B19013, B01003).
- **Shapefiles**: Illinois census tracts from [Census TIGER/Line 2023](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html) and Chicago city boundary from the [Chicago Data Portal](https://data.cityofchicago.org/Facilities-Geographic-Boundaries/Boundaries-City-Map/ewy2-6yfk).

## Data Processing

All processing is performed directly in `code/app.py` and `code/final project.qmd` with no separate preprocessing script.

1. Crime records are classified into four categories: Violent, Property, Regulatory, and Other.
2. ACS tables are processed to extract 11-digit GEOID tract codes and compute derived rates (education rate, unemployment rate, median income).
3. Illinois census tracts are clipped to the Chicago city boundary shapefile to exclude Cook County tracts outside the city.
4. Crime points are spatially joined to census tracts using a `within` predicate via GeoPandas `sjoin`.
5. Crime rate is computed as crime count per tract divided by ACS population, scaled per 100 residents.

## Project Structure
```
data/
  Crimes_-_2001_to_Present_20260304.csv  # Crime incidents filtered to 2024
  ACSDT5Y2024.B15003-Data.csv            # Educational attainment by tract
  ACSST5Y2024.S2301-Data.csv             # Unemployment rate by tract
  ACSDT5Y2024.B19013-Data.csv            # Median household income by tract
  ACSDT5Y2024.B01003-Data.csv            # Total population by tract
  tl_2023_17_tract/                      # Illinois census tract shapefile
  Boundaries - City_20260303/            # Chicago city boundary shapefile
code/
  app.py                                 # Streamlit dashboard
  final project.qmd                      # Writeup .qmd file
  final project.html                     # Writeup Knitted to HTML
  final-project.pdf                      # Writeup Knitted to PDF
```

## Usage
1. Run the Streamlit app locally:
```bash
   streamlit run code/app.py
```
2. Render the writeup:
```bash
   quarto render "code/final project.qmd" --to html
   quarto render "code/final project.qmd" --to pdf
```