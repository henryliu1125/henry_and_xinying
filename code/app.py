"""
Chicago Crime Dashboard — Streamlit app
Unified sidebar: Page selector at top, then page-specific filters below.
"""

from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

import json
import numpy as np
import pandas as pd
import geopandas as gpd
import plotly.express as px
import streamlit as st

# Page config
st.set_page_config(
    page_title="Chicago Crime Dashboard",
    page_icon="🔍",
    layout="wide",
)

# Crime classification helpers
VIOLENT = {
    "HOMICIDE", "BATTERY", "ASSAULT", "ROBBERY",
    "CRIMINAL SEXUAL ASSAULT", "SEX OFFENSE",
    "KIDNAPPING", "STALKING", "INTIMIDATION",
}
PROPERTY = {
    "THEFT", "BURGLARY", "MOTOR VEHICLE THEFT",
    "CRIMINAL DAMAGE", "CRIMINAL TRESPASS", "ARSON", "DECEPTIVE PRACTICE",
}
REGULATORY = {
    "NARCOTICS", "OTHER NARCOTIC VIOLATION", "LIQUOR LAW VIOLATION",
    "WEAPONS VIOLATION", "CONCEALED CARRY LICENSE VIOLATION", "GAMBLING",
    "PROSTITUTION", "PUBLIC INDECENCY", "OBSCENITY", "HUMAN TRAFFICKING",
}
ALL_TYPES = ["Violent", "Property", "Regulatory", "Other"]

def classify_crime(x):
    if x in VIOLENT:      return "Violent"
    elif x in PROPERTY:   return "Property"
    elif x in REGULATORY: return "Regulatory"
    else:                  return "Other"


# Data loaders (cached)
DATA_DIR = Path("data/derived-data")

@st.cache_data(show_spinner="Loading crime data...")
def load_crime():
    df = pd.read_csv(
        DATA_DIR / "Crimes_-_2001_to_Present_20260304.csv",
        usecols=["Date", "Primary Type", "Year", "Latitude", "Longitude"],
    )
    df["crime_type"] = df["Primary Type"].apply(classify_crime)
    df["Date"]  = pd.to_datetime(df["Date"], errors="coerce")
    df["month"] = df["Date"].dt.month
    df["hour"]  = df["Date"].dt.hour
    df = df.dropna(subset=["Latitude", "Longitude"])
    return df


@st.cache_data(show_spinner="Loading ACS data...")
def load_acs():
    # Education
    edu_raw = pd.read_csv(DATA_DIR / "ACSDT5Y2024.B15003-Data.csv")
    edu = edu_raw.iloc[3:][["GEO_ID","B15003_001E","B15003_021E",
                             "B15003_022E","B15003_023E","B15003_024E"]].copy()
    edu["tract_id"] = edu["GEO_ID"].str[-11:]
    num_cols = ["B15003_001E","B15003_021E","B15003_022E","B15003_023E","B15003_024E"]
    edu[num_cols] = edu[num_cols].apply(pd.to_numeric, errors="coerce")
    edu["edu_rate"] = 100 * (edu["B15003_021E"] + edu["B15003_022E"] +
                              edu["B15003_023E"] + edu["B15003_024E"]) / edu["B15003_001E"]
    edu = edu[["tract_id","edu_rate"]]

    # Unemployment
    unemp_raw = pd.read_csv(DATA_DIR / "ACSST5Y2024.S2301-Data.csv")
    unemp = unemp_raw.iloc[3:][["GEO_ID","S2301_C04_001E"]].copy()
    unemp["tract_id"] = unemp["GEO_ID"].str[-11:]
    unemp["unemployment_rate"] = pd.to_numeric(unemp["S2301_C04_001E"], errors="coerce")
    unemp = unemp[["tract_id","unemployment_rate"]]

    # Income
    income_raw = pd.read_csv(DATA_DIR / "ACSDT5Y2024.B19013-Data.csv")
    income = income_raw.iloc[3:][["GEO_ID","B19013_001E"]].copy()
    income["tract_id"] = income["GEO_ID"].str[-11:]
    income["median_income"] = pd.to_numeric(income["B19013_001E"], errors="coerce")
    income = income[["tract_id","median_income"]]

    # Population
    pop_raw = pd.read_csv(DATA_DIR / "ACSDT5Y2024.B01003-Data.csv")
    pop = pop_raw.iloc[3:][["GEO_ID","B01003_001E"]].copy()
    pop["tract_id"] = pop["GEO_ID"].str[-11:]
    pop["population"] = pd.to_numeric(pop["B01003_001E"], errors="coerce")
    pop = pop[["tract_id","population"]]

    return (pop
            .merge(edu,    on="tract_id", how="left")
            .merge(unemp,  on="tract_id", how="left")
            .merge(income, on="tract_id", how="left"))


@st.cache_data(show_spinner="Loading tract geometries...")
def load_tracts():
    tracts  = gpd.read_file(DATA_DIR / "tl_2023_17_tract" / "tl_2023_17_tract.shp")
    chicago = gpd.read_file(
        DATA_DIR / "Boundaries - City_20260303" /
        "geo_export_06d21f1c-6fda-4eae-9de6-a54e6cd59005.shp"
    )
    chicago = chicago.to_crs(tracts.crs)
    tracts_chi = (gpd.sjoin(tracts, chicago[["geometry"]],
                             how="inner", predicate="intersects")
                     .drop(columns=["index_right"]))
    tracts_chi = gpd.clip(tracts_chi, chicago)
    tracts_chi["GEOID"] = tracts_chi["GEOID"].astype(str).str.zfill(11)
    return tracts_chi.to_crs("EPSG:4326")


@st.cache_data(show_spinner="Spatial join crime to tracts...")
def assign_tracts(_crime_df, _tracts_gdf):
    crime_gdf = gpd.GeoDataFrame(
        _crime_df,
        geometry=gpd.points_from_xy(_crime_df["Longitude"], _crime_df["Latitude"]),
        crs="EPSG:4326",
    )
    joined = (gpd.sjoin(crime_gdf, _tracts_gdf[["GEOID","geometry"]],
                        how="inner", predicate="within")
                 .rename(columns={"GEOID":"tract_id"}))
    joined["tract_id"] = joined["tract_id"].astype(str).str.zfill(11)
    return pd.DataFrame(joined.drop(columns=["geometry","index_right"], errors="ignore"))


# Load all data 
crime_raw   = load_crime()
acs_all     = load_acs()
tracts_chi  = load_tracts()

# Filter ACS to Chicago tracts only 
chi_tract_ids = set(tracts_chi["GEOID"].astype(str).str.zfill(11))
acs = acs_all[acs_all["tract_id"].isin(chi_tract_ids)].copy()

crime_tract = assign_tracts(crime_raw, tracts_chi)

available_years = sorted(crime_tract["Year"].dropna().unique().astype(int), reverse=True)

# Fixed main title 
st.title("🔍 Chicago Crime Dashboard")


# UNIFIED SIDEBAR
with st.sidebar:
    st.markdown("## Filters")

    # Page selector (always visible) 
    st.markdown("**Page**")
    page = st.radio(
        label="page_radio",
        options=["Crime Distribution", "Socioeconomic Correlates"],
        index=0,
        label_visibility="collapsed",
    )

    st.markdown("---")

    # Year selector (always visible) 
    selected_year = st.selectbox("Year", options=available_years, index=0)

    st.markdown("---")

    # Page 1 — specific controls 
    if page == "Crime Distribution":

        month_range = st.slider(
            "Month range",
            min_value=1, max_value=12,
            value=(1, 12), step=1,
        )

        hour_range = st.slider(
            "Hour range",
            min_value=0, max_value=23,
            value=(0, 23), step=1,
        )

        selected_types = st.multiselect(
            "Crime categories",
            options=ALL_TYPES,
            default=ALL_TYPES,
            key="types_p1",
        )
        if not selected_types:
            st.warning("Select at least one category.")
            selected_types = ALL_TYPES

    # Page 2 — specific controls 
    else:
        factor = st.radio(
            "Socioeconomic factor",
            options=["Education rate", "Unemployment rate", "Median income"],
            index=0,
            key="factor_p2",
        )

        selected_types = st.multiselect(
            "Crime categories",
            options=ALL_TYPES,
            default=ALL_TYPES,
            key="types_p2",
        )
        if not selected_types:
            st.warning("Select at least one category.")
            selected_types = ALL_TYPES

        use_log = st.checkbox("Log scale for crime count (y-axis)", value=False)


# Filter to selected year 
crime_year = crime_tract[crime_tract["Year"] == selected_year]


# PAGE 1 — Map + Crime Type Bar
if page == "Crime Distribution":

    st.markdown("<h2 style='font-size:1.75rem; margin-bottom:0.25rem;'>🗺️ Crime Distribution (Geographical & Temporal)</h2>", unsafe_allow_html=True)

    # Apply time + type filters
    mask = (
        crime_year["month"].between(*month_range) &
        crime_year["hour"].between(*hour_range) &
        crime_year["crime_type"].isin(selected_types)
    )
    filtered = crime_year[mask]

    # Tract-level aggregation
    crime_by_tract = (
        filtered.groupby("tract_id", as_index=False)
        .size()
        .rename(columns={"size": "crime_count"})
    )
    tracts_agg = (
        tracts_chi[["GEOID","geometry"]]
        .merge(acs, left_on="GEOID", right_on="tract_id", how="left")
        .merge(crime_by_tract, left_on="GEOID", right_on="tract_id", how="left")
    )
    tracts_agg["crime_count"] = tracts_agg["crime_count"].fillna(0).astype(int)
    tracts_agg["crime_rate"]  = (tracts_agg["crime_count"] / tracts_agg["population"]) * 100
    geojson_dict = json.loads(tracts_agg.to_json())

    # Crime type counts for bar chart
    type_counts = (
        filtered.groupby("crime_type", as_index=False)
        .size()
        .rename(columns={"size": "crime_count"})
        .sort_values("crime_count", ascending=False)
    )

    # Charts
    col_map, col_bar = st.columns([3, 2])

    with col_map:
        st.markdown("<h3 style='text-align:center; font-size:1.1rem;'>Crime Rate by Census Tract</h3>", unsafe_allow_html=True)
        fig_map = px.choropleth_mapbox(
            tracts_agg,
            geojson=geojson_dict,
            locations="GEOID",
            featureidkey="properties.GEOID",
            color="crime_rate",
            color_continuous_scale="OrRd",
            mapbox_style="carto-positron",
            zoom=9.5,
            center={"lat": 41.8227, "lon": -87.6799},
            opacity=0.7,
            labels={"crime_rate": "Crime Rate (per 100)"},
            hover_data={
                "GEOID": True,
                "crime_count": True,
                "population": True,
                "crime_rate": ":.2f",
            },
        )
        fig_map.update_layout(
            margin={"r":0,"t":0,"l":0,"b":0},
            height=520,
            coloraxis_colorbar=dict(title="Crime Rate<br>(per 100 res.)"),
        )
        st.plotly_chart(fig_map, use_container_width=True)

    with col_bar:
        st.markdown("<h3 style='text-align:center; font-size:1.1rem;'>Crime Count by Category</h3>", unsafe_allow_html=True)
        COLOR_MAP = {
            "Violent":    "#d62728",
            "Property":   "#ff7f0e",
            "Regulatory": "#1f77b4",
            "Other":      "#7f7f7f",
        }
        fig_bar = px.bar(
            type_counts,
            x="crime_type",
            y="crime_count",
            color="crime_type",
            color_discrete_map=COLOR_MAP,
            labels={"crime_type": "Crime Category", "crime_count": "Crime Count"},
            text_auto=True,
        )
        fig_bar.update_layout(
            showlegend=False,
            height=520,
            xaxis_title="Crime Category",
            yaxis_title="Crime Count",
            plot_bgcolor="white",
            bargap=0.3,
        )
        fig_bar.update_traces(textposition="outside")
        st.plotly_chart(fig_bar, use_container_width=True)

    # Summary metrics
    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Crimes (filtered)", f"{len(filtered):,}")
    m2.metric("Tracts with Crimes", f"{(tracts_agg['crime_count'] > 0).sum()}")
    avg_rate = tracts_agg["crime_rate"].replace([np.inf, -np.inf], np.nan).dropna().mean()
    m3.metric("Avg Crime Rate (per 100)", f"{avg_rate:.2f}")


# PAGE 2 — Scatter: Crime vs Socioeconomic
else:
    st.markdown("<h2 style='font-size:1.75rem; margin-bottom:0.25rem;'>📊 Socioeconomic Correlates of Crime</h2>", unsafe_allow_html=True)

    FACTOR_MAP = {
        "Education rate":    ("edu_rate",          "Education Rate (% Bachelor+)"),
        "Unemployment rate": ("unemployment_rate", "Unemployment Rate (%)"),
        "Median income":     ("median_income",     "Median Household Income (USD)"),
    }
    factor_col, factor_label = FACTOR_MAP[factor]

    # Filter + aggregate
    filtered_t2 = crime_year[crime_year["crime_type"].isin(selected_types)]
    crime_by_tract_t2 = (
        filtered_t2.groupby("tract_id", as_index=False)
        .size()
        .rename(columns={"size": "crime_count"})
    )
    scatter_df = (
        acs[["tract_id","population", factor_col]]
        .merge(crime_by_tract_t2, on="tract_id", how="left")
    )
    scatter_df["crime_count"] = scatter_df["crime_count"].fillna(0).astype(int)
    scatter_df["crime_rate"]  = (scatter_df["crime_count"] / scatter_df["population"]) * 100
    scatter_df = scatter_df.dropna(subset=[factor_col])
    scatter_df = scatter_df[scatter_df["population"] > 0]

    def make_scatter(df, x_col, y_col, x_label, y_label, log_y, title):
        plot_df = df[[x_col, y_col, "tract_id"]].dropna()
        plot_df = plot_df[plot_df[y_col] >= 0]
        if log_y:
            plot_df = plot_df[plot_df[y_col] > 0]
        fig = px.scatter(
            plot_df,
            x=x_col, y=y_col,
            trendline="ols",
            labels={x_col: x_label, y_col: y_label},
            hover_data={"tract_id": True},
            log_y=log_y,
            opacity=0.55,
            color_discrete_sequence=["#d62728"],
        )
        fig.update_traces(marker=dict(size=6))
        fig.update_layout(
            height=490,
            plot_bgcolor="white",
            xaxis=dict(showgrid=True, gridcolor="#eeeeee"),
            yaxis=dict(showgrid=True, gridcolor="#eeeeee"),
        )
        return fig

    col_count, col_rate = st.columns(2)

    with col_count:
        st.markdown(f"<h3 style='text-align:center; font-size:1.1rem;'>Crime Count vs {factor}</h3>", unsafe_allow_html=True)
        st.plotly_chart(
            make_scatter(scatter_df, factor_col, "crime_count",
                         factor_label, "Crime Count", use_log,
                         f"Crime Count vs {factor_label}"),
            use_container_width=True,
        )

    with col_rate:
        st.markdown(f"<h3 style='text-align:center; font-size:1.1rem;'>Crime Rate vs {factor}</h3>", unsafe_allow_html=True)
        st.plotly_chart(
            make_scatter(scatter_df, factor_col, "crime_rate",
                         factor_label, "Crime Rate (per 100 residents)", False,
                         f"Crime Rate vs {factor_label}"),
            use_container_width=True,
        )

    # Correlation stats 
    st.markdown("---")
    valid = scatter_df[[factor_col, "crime_count", "crime_rate"]].dropna()
    corr_count = valid[factor_col].corr(valid["crime_count"])
    corr_rate  = valid[factor_col].corr(valid["crime_rate"])

    c1, c2, c3 = st.columns(3)
    c1.metric(f"Pearson r  ({factor} vs Count)", f"{corr_count:.3f}")
    c2.metric(f"Pearson r  ({factor} vs Rate)",  f"{corr_rate:.3f}")
    c3.metric("Tracts included", f"{len(valid):,}")