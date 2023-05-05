import pandas as pd
import numpy as np
import streamlit as st
import altair as alt
import re
import requests

# I added this to cache and grab the data from a google cloud bucket

@st.cache_data
def get_property_data():
    # Load the data
    url = st.secrets["property_url"]    
    properties = pd.read_csv(url)
    return properties


# Load the data and filter it
properties = get_property_data()

# Define a dictionary with the correct data types for each column
column_types = {
    "COMPANY_NAME": str,
    "REPORTINGPERIODENDDATE": "datetime64[ns]",
    "PHYSICALOCCUPANCYSECURITIZATIONPERCENTAGE": float,
    "PROPERTYSTATE": str,
    "MOST_RECENT_VALUE": int
}

# Extract unique years from COMPANY_NAME
unique_years = sorted(list(set([int(re.findall(r'(?<=\D)\d{4}(?=\D|$)', name)[0]) for name in properties['COMPANY_NAME'].unique()])))

# Provide a title on the page
st.title( "Occupancy Rates by Vintage")

# Create a dropdown menu in Streamlit with the list of unique years
selected_year = st.selectbox("Select a Vintage:", unique_years, index=2)

# Filter the data based on the selected year
year_data = properties[properties["COMPANY_NAME"].str.contains(str(selected_year))].copy()


# Get the unique companies for the selected year
unique_companies = year_data["COMPANY_NAME"].unique().tolist()

# Create a dropdown menu in Streamlit with the list of unique companies
selected_company = st.selectbox("Select a Company:", unique_companies)

# Clean up the data

# Fill missing values with 0 in the 'MOST_RECENT_VALUE' column
year_data['MOST_RECENT_VALUE'] = year_data['MOST_RECENT_VALUE'].fillna(0)

# Apply transformations to the 'PHYSICALOCCUPANCYSECURITIZATIONPERCENTAGE' column
year_data['PHYSICALOCCUPANCYSECURITIZATIONPERCENTAGE'] = year_data['PHYSICALOCCUPANCYSECURITIZATIONPERCENTAGE'].apply(
    lambda x: x / 100 if x > 1 else x).fillna(0)

# Drop rows with missing REPORTINGPERIODENDDATE
year_data = year_data.dropna(subset=['REPORTINGPERIODENDDATE'])

# Convert the data types of the columns in the properties DataFrame
year_data = year_data.astype(column_types)

# Filter for BANK 2020-BANK25
bank_data = year_data[year_data["COMPANY_NAME"] == selected_company].copy()

year_data["REPORTINGPERIODENDDATE"] = pd.to_datetime(year_data["REPORTINGPERIODENDDATE"]) - pd.offsets.MonthBegin(1)
bank_data["REPORTINGPERIODENDDATE"] = pd.to_datetime(bank_data["REPORTINGPERIODENDDATE"]) - pd.offsets.MonthBegin(1)


# Group by REPORTINGPERIODENDDATE and calculate the weighted occupancy
bank_weighted_occupancy = (
    bank_data
    .groupby("REPORTINGPERIODENDDATE", as_index=False)
    .apply(lambda x: np.average(x["PHYSICALOCCUPANCYSECURITIZATIONPERCENTAGE"], weights=x["MOST_RECENT_VALUE"]))
    .reset_index(drop=True)
)

bank_weighted_occupancy.columns = ["REPORTINGPERIODENDDATE", "weighted_occupancy"]

#print( bank_weighted_occupancy)

# Calculate the 25th, 50th, and 75th percentiles for all deals
percentiles = (
    year_data
    .groupby("REPORTINGPERIODENDDATE", as_index=False)
    .apply(lambda x: pd.Series(np.percentile(x["PHYSICALOCCUPANCYSECURITIZATIONPERCENTAGE"], [25, 50, 75]), index=["P25", "P50", "P75"]))
    .reset_index()
)

percentiles.rename(columns={"level_1": "REPORTINGPERIODENDDATE", "P25": "p25", "P50": "p50", "P75": "p75"}, inplace=True)

min_occupancy = (percentiles['p25'].min() - 0.01 )
max_occupancy = (percentiles['p75'].max() + 0.001 )

#print( percentiles )
# Create the line chart for BANK 2020-BANK25
bank_line = alt.Chart(bank_weighted_occupancy).mark_line(color='black').encode(
    x= alt.X('REPORTINGPERIODENDDATE:T', axis=alt.Axis(title="Reporting Date", labelAngle=-45, format = ("%b %Y"))),
    y= alt.Y('weighted_occupancy:Q', scale=alt.Scale(domain=[ min_occupancy , max_occupancy ], clamp=True), axis=alt.Axis(title="Weighted Average Occupancy Rate", format="%"))
)

# Create the line chart for the 25th percentile
p25_line = alt.Chart(percentiles).mark_line(color='grey', strokeDash=[3,3]).encode(
    x='REPORTINGPERIODENDDATE:T',
    y= alt.Y('p25:Q', scale=alt.Scale(domain=[ min_occupancy , max_occupancy ], clamp=True), axis=alt.Axis( format="%"))
)

# Create the line chart for the 50th percentile
p50_line = alt.Chart(percentiles).mark_line(color='grey', strokeDash=[3,3]).encode(
    x='REPORTINGPERIODENDDATE:T',
    y= alt.Y('p50:Q', scale=alt.Scale(domain=[ min_occupancy , max_occupancy ], clamp=True), axis=alt.Axis( format="%"))
)

# Create the line chart for the 75th percentile
p75_line = alt.Chart(percentiles).mark_line(color='grey', strokeDash=[3,3]).encode(
    x='REPORTINGPERIODENDDATE:T',
    y= alt.Y('p75:Q', scale=alt.Scale(domain=[ min_occupancy , max_occupancy ], clamp=True), axis=alt.Axis( format="%"))
)

# Combine the line charts into a single chart
chart = alt.layer(bank_line, p25_line, p50_line, p75_line).resolve_scale(y='shared').properties(    
    height=500  # Set the height of the chart
)

with st.container():
    st.divider()

    # Display the chart
    st.altair_chart(chart, use_container_width=True)

with st.expander("See explanation"):
    st.write("The chart above reflects the weighted average occupancy rate by month for the selected company. The dotted lines represent the 25th, 50th and 75th percentile weighted average occupancy rates for the selected vintage.")

st.write("To read more about how this was created, check out the following Substack post [link](https://www.prompts.finance/p/cmbs-occupancy-rates)")