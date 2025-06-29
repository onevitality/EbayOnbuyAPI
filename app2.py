import streamlit as st
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
        # 1) Pull raw lists to count orders
        onbuy_list = get_onbuy_orders(get_onbuy_token())
        ebay_list  = get_ebay_orders(get_ebay_token())
        onbuy_count = len(onbuy_list)
        ebay_count  = len(ebay_list)
        total_count = onbuy_count + ebay_count

        # 2) Build aggregated DataFrame
        df = build_report_df()

    # — Display metrics —
    col1, col2, col3 = st.columns(3)
    col1.metric("Total eBay Orders", ebay_count)
    col2.metric("Total OnBuy Orders", onbuy_count)
    col3.metric("Total Orders", total_count)

    # — Show table & download —
    st.success(f"Aggregated {len(df)} products sold")
    st.dataframe(df, use_container_width=True)
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", data=csv, file_name="combined_report.csv")
