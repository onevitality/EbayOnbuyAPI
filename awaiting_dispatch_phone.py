import requests
import base64
import pandas as pd
import ast

# — Configuration: replace with your real secrets —
ONBUY_CONSUMER_KEY = "ck_live_36f7d198893e4d55a95db09e106c03d2"
ONBUY_SECRET_KEY   = "sk_live_2f420836ad73482b85db95a4c51597f2"

EBAY_CLIENT_ID     = "Samerjee-Inventor-PRD-3dc6cc3e0-579dd8d5"
EBAY_CLIENT_SECRET = "PRD-dc6cc3e099d7-3406-41ed-b530-0975"
EBAY_REFRESH_TOKEN = "v^1.1#i^1#f^0#p^3#I^3#r^1#t^Ul4xMF81OkYwQTcwRDI5RDEwQzQyNERFNEJCRThBOUY4NDU4MUNGXzFfMSNFXjI2MA=="

MAPPING_FILE = "Product ID Table.xlsx"

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
                "sku":              p.get("sku"),
                "onbuy_quantity":   int(p.get("quantity", 0))
            })
    df = pd.DataFrame(rows)
    if df.empty:
        # ensure columns exist even if no rows
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
        params={
            "filter": "orderfulfillmentstatus:{NOT_STARTED|IN_PROGRESS}",
            "limit":  100
        }
    )
    r.raise_for_status()
    orders = r.json().get("orders", [])
    # keep only awaiting dispatch
    return [o for o in orders if o.get("orderFulfillmentStatus") == "NOT_STARTED"]

def process_ebay(orders):
    rows = []
    for o in orders:
        for li in o.get("lineItems", []):
            rows.append({
                "sku":             li.get("sku"),
                "ebay_quantity":   int(li.get("quantity", 0))
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["sku", "ebay_quantity"])
    return df.groupby("sku", as_index=False)["ebay_quantity"].sum()

# — This is the function your Streamlit app will call —
def build_report_df():
    # 1) fetch & aggregate
    df_onbuy = process_onbuy(get_onbuy_orders(get_onbuy_token()))
    df_ebay  = process_ebay(get_ebay_orders(get_ebay_token()))

    # 2) join SKUs (now guaranteed to have 'sku')
    df = pd.merge(df_onbuy, df_ebay, on="sku", how="outer").fillna(0)
    df["onbuy_quantity"] = df["onbuy_quantity"].astype(int)
    df["ebay_quantity"]  = df["ebay_quantity"].astype(int)
    df["total_quantity"] = df["onbuy_quantity"] + df["ebay_quantity"]

    # 3) map names
    mapping = pd.read_excel(MAPPING_FILE, usecols="C:D")
    mapping.columns = mapping.columns.str.strip().str.lower().str.replace(" ", "_")
    mapping = (
        mapping.rename(columns={"sku":"sku", "product_name":"product_name"})
               .drop_duplicates(subset=["sku"])
    )

    df = pd.merge(df, mapping, on="sku", how="left")
    df["product_name"] = df["product_name"].fillna("unknown")

    # 4) filter sold only and order
    df = df.loc[
        df["total_quantity"] > 0,
        ["product_name","onbuy_quantity","ebay_quantity","total_quantity","sku"]
    ]
    return df.sort_values("product_name")

# — If you ever run this module directly, it’ll write Excel —
if __name__ == "__main__":
    df = build_report_df()
    df.to_excel("combined_products_sales.xlsx", index=False)
    print(f"✅ Written combined_products_sales.xlsx with {len(df)} rows")
