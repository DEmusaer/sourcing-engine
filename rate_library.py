# rate_library.py
#
# This is the replacement for a paid BCIS subscription: a local, business-owned
# rate database that starts empty (or seeded from your own historical spreadsheets)
# and grows every time a human confirms a real rate or a real supplier quote comes in.
#
# Hard rule: nothing in this file ever invents a price. A rate either exists in the
# library (entered by a human, or confirmed from a real supplier quote) or the item
# is flagged as unpriced. No LLM call happens anywhere in this module.

import os
import difflib
from datetime import date

import pandas as pd

# DATA_DIR defaults to the current folder for a normal local run. Inside Docker,
# this points at a mounted volume instead, so the rate library survives a
# container restart rather than being wiped every time.
DATA_DIR = os.environ.get("DATA_DIR", ".")
RATE_LIBRARY_PATH = os.path.join(DATA_DIR, "rate_library.csv")
COLUMNS = ["item_code", "description", "unit", "rate_gbp", "source", "last_updated"]


def load_rates() -> pd.DataFrame:
    """Load the rate library, creating an empty one if it doesn't exist yet."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(RATE_LIBRARY_PATH):
        df = pd.DataFrame(columns=COLUMNS)
        df.to_csv(RATE_LIBRARY_PATH, index=False)
        return df
    return pd.read_csv(RATE_LIBRARY_PATH)


def save_rate(description: str, unit: str, rate_gbp: float, source: str = "Manual entry", item_code: str = "") -> pd.DataFrame:
    """Add or update a rate. Matching is on description (case-insensitive exact match);
    a new description creates a new row. Returns the updated library."""
    df = load_rates()
    description_norm = description.strip()
    mask = df["description"].astype(str).str.strip().str.lower() == description_norm.lower()

    if mask.any():
        idx = df[mask].index[0]
        df.loc[idx, ["unit", "rate_gbp", "source", "last_updated"]] = [unit, rate_gbp, source, str(date.today())]
    else:
        new_row = {
            "item_code": item_code or f"ITEM-{len(df) + 1:04d}",
            "description": description_norm,
            "unit": unit,
            "rate_gbp": rate_gbp,
            "source": source,
            "last_updated": str(date.today()),
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    df.to_csv(RATE_LIBRARY_PATH, index=False)
    return df


def import_rates_csv(uploaded_df: pd.DataFrame, source_label: str = "Bulk import") -> pd.DataFrame:
    """Bulk-seed the library from an existing spreadsheet of historical rates.
    Expects at minimum 'description', 'unit', 'rate_gbp' columns (case-insensitive).
    This is how you seed the library from your own old cost plans instead of BCIS."""
    normalized = {c.lower().strip(): c for c in uploaded_df.columns}
    required = ["description", "unit", "rate_gbp"]
    missing = [r for r in required if r not in normalized]
    if missing:
        raise ValueError(f"Uploaded file is missing required columns: {missing}. Found: {list(uploaded_df.columns)}")

    for _, row in uploaded_df.iterrows():
        save_rate(
            description=str(row[normalized["description"]]),
            unit=str(row[normalized["unit"]]),
            rate_gbp=float(row[normalized["rate_gbp"]]),
            source=source_label,
        )
    return load_rates()


def find_rate(description: str, rates_df: pd.DataFrame, cutoff: float = 0.6):
    """Fuzzy-match a line item description against the library.
    Returns the matching row (as a dict) or None if nothing close enough exists.
    This is deliberately simple string matching, not an LLM guess - if it's wrong,
    it's wrong in an auditable, debuggable way."""
    if rates_df.empty:
        return None

    descriptions = rates_df["description"].astype(str).tolist()
    matches = difflib.get_close_matches(description, descriptions, n=1, cutoff=cutoff)
    if not matches:
        return None

    row = rates_df[rates_df["description"] == matches[0]].iloc[0]
    return row.to_dict()
