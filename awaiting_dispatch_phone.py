import requests
import base64
import pandas as pd
import ast

# — Configuration: replace with your real secrets —
ONBUY_CONSUMER_KEY = "ck_live_36f7d198893e4d55a95db09e106c03d2"
ONBUY_SECRET_KEY   = "sk_live_2f420836ad73482b85db95a4c51597f2"

EBAY_CLIENT_ID     = "JasalKhu-Inventor-PRD-480eb0c02-ce273d1d"
EBAY_CLIENT_SECRET = "PRD-80eb0c024054-e725-494d-8435-1114"
EBAY_REFRESH_TOKEN = "v^1.1#i^1#f^0#p^3#I^3#r^1#t^Ul4xMF8xMDo2NUU2QTVCMTM1MEEwNjg2NjVCNTgxQjdFNUI1NjBERV8xXzEjRV4yNjA"

MAPPING_FILE = "Product ID Table.xlsx"  # Ensure this file has columns: SKU, Product Name, Group SKU

# — OnBuy helpers —
def get_onbuy_token():
    r = requests.post(
        "https://api.onbuy.com/v2/auth/request-token",
        files={
            'consumer_key': (None, ONBUY_CONSUMER_KEY),
            'secret_key':   (None, ONBUY_SECRET_KEY)
        }
    )
    r.raise_for_status()
    return r.json()["access_token"]

def get_onbuy_orders(token):
    r = requests.get(
        "https://api.onbuy.com/v2/orders",
        headers={"Authorization": token},
        params={
            "site_id":        2000,
            "filter[status]": "awaiting_dispatch",
            "sort[created]":  "desc",
            "limit":          100,
            "offset":         0
        }
    )
    r.raise_for_status()
    return r.json().get("results", [])

def process_onbuy(orders):
    rows = []
    for o in orders:
        prods = o.get("products") or []
        if isinstance(prods, str):
            try:
                prods = ast.literal_eval(prods)
            except:
                prods = []
        for p in prods:
            rows.append({
                "sku":            p.get("sku"),
                "onbuy_quantity": int(p.get("quantity", 0))
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["sku", "onbuy_quantity"])
    return df.groupby("sku", as_index=False)["onbuy_quantity"].sum()

# — eBay helpers —
def get_ebay_token():
    creds = f"{EBAY_CLIENT_ID}:{EBAY_CLIENT_SECRET}"
    b64   = base64.b64encode(creds.encode()).decode()
    r = requests.post(
        "https://api.ebay.com/identity/v1/oauth2/token",
        headers={
            "Authorization": f"Basic {b64}",
            "Content-Type":  "application/x-www-form-urlencoded"
        },
        data={
            "grant_type":    "refresh_token",
            "refresh_token": EBAY_REFRESH_TOKEN,
            "scope":         "https://api.ebay.com/oauth/api_scope/sell.fulfillment.readonly"
        }
    )
    r.raise_for_status()
    return r.json()["access_token"]

def get_ebay_orders(token):
    r = requests.get(
        "https://api.ebay.com/sell/fulfillment/v1/order",
        headers={"Authorization": f"Bearer {token}"},
        params={"filter": "orderfulfillmentstatus:{NOT_STARTED|IN_PROGRESS}", "limit": 100}
    )
    r.raise_for_status()
    orders = r.json().get("orders", [])
    return [o for o in orders if o.get("orderFulfillmentStatus") == "NOT_STARTED"]

def process_ebay(orders):
    rows = []
    for o in orders:
        for li in o.get("lineItems", []):
            rows.append({
                "sku":           li.get("sku"),
                "ebay_quantity": int(li.get("quantity", 0))
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["sku", "ebay_quantity"])
    return df.groupby("sku", as_index=False)["ebay_quantity"].sum()

# — Build combined report DataFrame, now grouped by Group SKU —
def build_report_df():
    # fetch & aggregate each marketplace
    df_onbuy = process_onbuy(get_onbuy_orders(get_onbuy_token()))
    df_ebay  = process_ebay(get_ebay_orders(get_ebay_token()))

    # merge and compute totals by SKU
    df = pd.merge(df_onbuy, df_ebay, on="sku", how="outer").fillna(0)
    df["onbuy_quantity"] = df["onbuy_quantity"].astype(int)
    df["ebay_quantity"]  = df["ebay_quantity"].astype(int)

    # load mapping including Group SKU
    mapping = pd.read_excel(MAPPING_FILE, usecols="C:D,G")
    mapping.columns = (
        mapping.columns
            .str.strip()
            .str.lower()
            .str.replace(" ", "_")
    )  # ['sku', 'product_name', 'group_sku']
    mapping = mapping.drop_duplicates(subset=["sku"])

    # attach product_name and group_sku to each row
    df = pd.merge(df, mapping, on="sku", how="left")
    df["product_name"] = df["product_name"].fillna("unknown")
    # default group_sku to own sku if missing
    df["group_sku"] = df["group_sku"].fillna(df["sku"])

    # aggregate by group_sku (and product_name for readability)
    df_grouped = (
        df
        .groupby(["group_sku", "product_name"], as_index=False)
        .agg({
            "onbuy_quantity": "sum",
            "ebay_quantity":  "sum"
        })
    )
    df_grouped["total_quantity"] = (
        df_grouped["onbuy_quantity"] + df_grouped["ebay_quantity"]
    )

    # filter out zero sales and sort by product_name
    df_final = (
        df_grouped
        .loc[df_grouped["total_quantity"] > 0,
             ["product_name", "total_quantity", "ebay_quantity", "onbuy_quantity", "group_sku"]]
        .sort_values("product_name")
    )

    return df_final

# — If run directly, write to Excel —
if __name__ == "__main__":
    df = build_report_df()
    df.to_excel("combined_products_sales_by_group.xlsx", index=False)
    print(f"✅ Written combined_products_sales_by_group.xlsx with {len(df)} rows")
