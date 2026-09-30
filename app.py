# app.py
# Main Streamlit entry point for the sourcing engine

import streamlit as st
import pandas as pd
from rate_library import load_rates, save_rate, import_rates_csv, find_rate
from sourcing_engine import compare_quotes, comparison_summary

st.set_page_config(page_title="Sourcing Engine", layout="wide")
st.title("Construction Sourcing Engine")

# Sidebar: Rate Library Management
with st.sidebar:
    st.header("Rate Library")
    
    # View current rates
    rates_df = load_rates()
    st.subheader(f"Rates in Library ({len(rates_df)})")
    st.dataframe(rates_df, use_container_width=True, hide_index=True)
    
    st.divider()
    
    # Add single rate
    st.subheader("Add Single Rate")
    col1, col2 = st.columns(2)
    with col1:
        desc = st.text_input("Description")
        unit = st.text_input("Unit")
    with col2:
        rate = st.number_input("Rate (GBP)", min_value=0.0, format="%.2f")
    
    if st.button("Save Rate"):
        if desc and unit and rate > 0:
            save_rate(desc, unit, rate)
            st.success("Rate saved!")
            st.rerun()
        else:
            st.error("Please fill in all fields")
    
    st.divider()
    
    # Bulk import
    st.subheader("Bulk Import Rates")
    uploaded_file = st.file_uploader("Upload CSV (requires description, unit, rate_gbp columns)", type="csv")
    if uploaded_file:
        try:
            import_df = pd.read_csv(uploaded_file)
            import_rates_csv(import_df, source_label="Bulk import")
            st.success(f"Imported {len(import_df)} rates!")
            st.rerun()
        except Exception as e:
            st.error(f"Import failed: {e}")


# Main: Quote Comparison
st.header("Quote Comparison")

# BOQ input
st.subheader("Bill of Quantities (BOQ)")
boq_csv = st.text_area(
    "Paste BOQ as CSV (description,quantity,unit)",
    height=100,
    placeholder="Carpet tile,100,SF\nConcrete block,500,EA"
)

# Supplier quotes input
st.subheader("Supplier Quotes")
quotes_csv = st.text_area(
    "Paste supplier quotes as CSV (description,unit_price,lead_time_days,supplier)",
    height=100,
    placeholder="Carpet tile,15.0,5,Supplier A\nCarpet tile,12.5,10,Supplier B"
)

if st.button("Compare"):
    try:
        # Parse BOQ
        if not boq_csv.strip():
            st.error("Please enter BOQ data")
        else:
            from io import StringIO
            boq_lines = [line.split(',') for line in boq_csv.strip().split('\n')]
            boq_items = [
                {"description": line[0].strip(), "quantity": float(line[1]), "unit": line[2].strip()}
                for line in boq_lines if len(line) >= 3
            ]
            
            # Parse quotes
            if not quotes_csv.strip():
                st.warning("No quotes provided - BOQ items will show as unmatched")
                combined_quotes = pd.DataFrame(columns=["description", "unit_price", "lead_time_days", "supplier"])
            else:
                quote_lines = [line.split(',') for line in quotes_csv.strip().split('\n')]
                quote_data = [
                    {
                        "description": line[0].strip(),
                        "unit_price": float(line[1]),
                        "lead_time_days": float(line[2]) if len(line) > 2 else None,
                        "supplier": line[3].strip() if len(line) > 3 else "Unknown"
                    }
                    for line in quote_lines if len(line) >= 2
                ]
                combined_quotes = pd.DataFrame(quote_data)
            
            # Run comparison
            comparison = compare_quotes(boq_items, combined_quotes)
            summary = comparison_summary(comparison)
            
            # Display results
            st.subheader("Results")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total (Cheapest)", f"£{summary['total_cheapest_gbp']:,.2f}")
            col2.metric("Matched", summary['matched_count'])
            col3.metric("Unmatched", summary['unmatched_count'])
            
            st.dataframe(comparison, use_container_width=True, hide_index=True)
            
            # Download results
            csv = comparison.to_csv(index=False)
            st.download_button(
                label="Download Comparison as CSV",
                data=csv,
                file_name="sourcing_comparison.csv",
                mime="text/csv"
            )
    
    except Exception as e:
        st.error(f"Error: {e}")
