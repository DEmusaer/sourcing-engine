# sourcing_engine.py
#
# Stage 7: takes quotes from multiple suppliers (10-50, per the real workflow this
# was built for) and matches them against the current BOQ line items. For each
# item it surfaces the cheapest quote AND the fastest lead time - separately,
# since the cheapest supplier isn't always the fastest one - and leaves the final
# call to the PM. Nothing here picks a "winner" automatically; it narrows the
# decision, it doesn't make it.

import difflib

import pandas as pd


def find_matching_quotes(description: str, combined_df: pd.DataFrame, cutoff: float = 0.6) -> pd.DataFrame:
    """All supplier quote rows whose description is a close match to this BOQ item.
    Deliberately returns every close match, not just one - a BOQ item may be
    quoted by several suppliers, and we want all of them to compare."""
    if combined_df.empty:
        return combined_df.iloc[0:0]
    descriptions = list(set(combined_df["description"].astype(str).tolist()))
    close = difflib.get_close_matches(str(description), descriptions, n=20, cutoff=cutoff)
    if not close:
        return combined_df.iloc[0:0]
    return combined_df[combined_df["description"].astype(str).isin(close)]


def compare_quotes(boq_items: list, combined_quotes: pd.DataFrame) -> pd.DataFrame:
    """boq_items: list of dicts with 'description', 'quantity', 'unit'.
    combined_quotes: DataFrame with columns 'description', 'unit_price', 'lead_time_days', 'supplier'.
    Returns one row per BOQ item with the cheapest and fastest matching quote."""
    rows = []
    for item in boq_items:
        description = str(item.get("description", "")).strip()
        try:
            quantity = float(item.get("quantity", 0) or 0)
        except (TypeError, ValueError):
            quantity = 0.0
        unit = str(item.get("unit", "")).strip()

        if not description:
            continue

        matches = find_matching_quotes(description, combined_quotes)

        if matches.empty:
            rows.append({
                "description": description, "quantity": quantity, "unit": unit,
                "cheapest_supplier": None, "cheapest_price": None, "cheapest_lead_time": None,
                "fastest_supplier": None, "fastest_price": None, "fastest_lead_time": None,
                "quotes_count": 0, "cheapest_subtotal": None, "status": "NO QUOTES",
            })
            continue

        matches = matches.copy()
        matches["unit_price"] = pd.to_numeric(matches["unit_price"], errors="coerce")
        matches["lead_time_days"] = pd.to_numeric(matches.get("lead_time_days"), errors="coerce")
        priced = matches.dropna(subset=["unit_price"])

        if priced.empty:
            rows.append({
                "description": description, "quantity": quantity, "unit": unit,
                "cheapest_supplier": None, "cheapest_price": None, "cheapest_lead_time": None,
                "fastest_supplier": None, "fastest_price": None, "fastest_lead_time": None,
                "quotes_count": len(matches), "cheapest_subtotal": None, "status": "QUOTES FOUND, NO VALID PRICE",
            })
            continue

        cheapest = priced.loc[priced["unit_price"].idxmin()]
        with_lead_time = priced.dropna(subset=["lead_time_days"])
        fastest = with_lead_time.loc[with_lead_time["lead_time_days"].idxmin()] if not with_lead_time.empty else cheapest

        rows.append({
            "description": description,
            "quantity": quantity,
            "unit": unit,
            "cheapest_supplier": cheapest.get("supplier"),
            "cheapest_price": cheapest["unit_price"],
            "cheapest_lead_time": cheapest.get("lead_time_days"),
            "fastest_supplier": fastest.get("supplier"),
            "fastest_price": fastest["unit_price"],
            "fastest_lead_time": fastest.get("lead_time_days"),
            "quotes_count": len(priced),
            "cheapest_subtotal": round(quantity * cheapest["unit_price"], 2),
            "status": "Matched",
        })

    return pd.DataFrame(rows)


def comparison_summary(comparison_df: pd.DataFrame) -> dict:
    if comparison_df.empty:
        return {"total_cheapest_gbp": 0.0, "matched_count": 0, "unmatched_count": 0}
    matched = comparison_df[comparison_df["status"] == "Matched"]
    unmatched = comparison_df[comparison_df["status"] != "Matched"]
    return {
        "total_cheapest_gbp": round(matched["cheapest_subtotal"].sum(), 2) if not matched.empty else 0.0,
        "matched_count": len(matched),
        "unmatched_count": len(unmatched),
    }
