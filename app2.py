APP_VERSION = "app2.py deployed 2025-07-20 15:10 test A"
import streamlit as st
st.sidebar.info(APP_VERSION)

from awaiting_dispatch_phone import (
    build_report_df,
    get_onbuy_token, get_onbuy_orders,
    get_ebay_token,  get_ebay_orders
)

# — Page layout —
st.set_page_config(page_title="OnBuy + eBay Report", layout="wide")
st.title("📊 OnBuy + eBay Awaiting Dispatch Sales")
st.write("Click the button below to fetch the latest report:")

# — Fetch button —
if st.button("Fetch & Refresh Report"):
    with st.spinner("Pulling data… this can take a moment"):
        onbuy_list = get_onbuy_orders(get_onbuy_token())
        ebay_list  = get_ebay_orders(get_ebay_token())
        onbuy_count = len(onbuy_list)
        ebay_count  = len(ebay_list)
        total_count = onbuy_count + ebay_count
        df = build_report_df()

    # Move index to last column (row_id) before displaying
    df_display = df.reset_index().rename(columns={'index': 'row_id'})
    cols = [c for c in df_display.columns if c != 'row_id'] + ['row_id']
    df_display = df_display[cols]

    col1, col2, col3 = st.columns(3)
    col1.metric("Total eBay Orders", ebay_count)
    col2.metric("Total OnBuy Orders", onbuy_count)
    col3.metric("Total Orders", total_count)

    st.success(f"Aggregated {len(df_display)} products sold")
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    st.download_button(
        "Download CSV",
        data=df_display.to_csv(index=False).encode("utf-8"),
        file_name="combined_report.csv"
    )

