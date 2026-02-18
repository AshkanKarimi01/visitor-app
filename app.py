import streamlit as st
import pandas as pd
import datetime
import os
import time

# --- تنظیمات صفحه ---
st.set_page_config(page_title="سیستم پخش مویرگی", layout="centered", page_icon="🚛")

# --- تنظیمات مسیر ذخیره‌سازی (برای لیارا و دکر) ---
DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

CUSTOMERS_DB = os.path.join(DATA_DIR, "customers_db.csv")
ORDERS_DB = os.path.join(DATA_DIR, "orders_db.csv")
PRODUCT_FILE = "products.csv"

@st.cache_data
def load_products():
    try:
        if not os.path.exists(PRODUCT_FILE):
            return pd.DataFrame()
        
        # خواندن فایل با حذف ردیف‌های کاملاً خالی
        df = pd.read_csv(PRODUCT_FILE).dropna(how='all')
        
        # استانداردسازی نام ستون‌ها (حذف فاصله‌ها و تبدیل ک و ی عربی به فارسی)
        df.columns = [c.strip().replace('ك', 'ک').replace('ي', 'ی') for c in df.columns]
        
        # استانداردسازی محتوای ستون‌ها (اگر ستون متنی است)
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip().str.replace('ك', 'ک').str.replace('ي', 'ی')
            
        return df
    except Exception as e:
        st.error(f"خطا در بارگذاری لیست کالاها: {e}")
        return pd.DataFrame()

def load_customers():
    if os.path.exists(CUSTOMERS_DB):
        try:
            return pd.read_csv(CUSTOMERS_DB)
        except:
            return pd.DataFrame(columns=["Name", "Address", "Phone", "Type"])
    else:
        return pd.DataFrame(columns=["Name", "Address", "Phone", "Type"])

def save_customer(name, address, phone, c_type):
    df = load_customers()
    # استانداردسازی نام برای جستجوی دقیق‌تر
    name = name.strip().replace('ك', 'ک').replace('ي', 'ی')
    
    if not df.empty and name in df["Name"].values:
        df.loc[df["Name"] == name, ["Address", "Phone", "Type"]] = [address, phone, c_type]
    else:
        new_row = pd.DataFrame({"Name": [name], "Address": [address], "Phone": [phone], "Type": [c_type]})
        df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(CUSTOMERS_DB, index=False)

def save_order(invoice_no, date, customer_name, items_df):
    to_save = items_df.copy()
    to_save["InvoiceNo"] = invoice_no
    to_save["Date"] = date
    to_save["Customer"] = customer_name
    
    if not os.path.exists(ORDERS_DB):
        to_save.to_csv(ORDERS_DB, index=False)
    else:
        to_save.to_csv(ORDERS_DB, mode='a', header=False, index=False)

# --- رابط کاربری ---

st.title("🚛 ثبت سفارش پخش مویرگی")
st.write("---")

# 1. بخش اطلاعات مشتری
st.header("👤 مشخصات مشتری")

customers_df = load_customers()
existing_names = customers_df["Name"].tolist() if not customers_df.empty else []

search_mode = st.radio("وضعیت مشتری:", ["مشتری جدید", "جستجوی مشتری قدیم"], horizontal=True)

name_input = ""
address_input = ""
phone_input = ""
type_input = "نانوایی"

if search_mode == "جستجوی مشتری قدیم" and existing_names:
    selected_name = st.selectbox("نام مشتری را انتخاب کنید:", [""] + existing_names)
    if selected_name:
        cust_data = customers_df[customers_df["Name"] == selected_name].iloc[0]
        name_input = selected_name
        address_input = cust_data["Address"]
        phone_input = cust_data["Phone"]
        type_input = cust_data["Type"]
elif search_mode == "جستجوی مشتری قدیم" and not existing_names:
    st.warning("هنوز مشتری در دیتابیس ثبت نشده است.")
    name_input = st.text_input("نام و نام خانوادگی:")
else:
    name_input = st.text_input("نام و نام خانوادگی:")

with st.container():
    col1, col2 = st.columns(2)
    with col1:
        final_name = st.text_input("تایید نام:", value=name_input, disabled=(search_mode=="جستجوی مشتری قدیم" and name_input!=""))
        c_type = st.selectbox("صنف:", ["نانوایی", "کبابی", "سایر"], 
                             index=["نانوایی", "کبابی", "سایر"].index(type_input) if type_input in ["نانوایی", "کبابی", "سایر"] else 0)
    with col2:
        phone = st.text_input("شماره تلفن:", value=phone_input)
    address = st.text_area("آدرس:", value=address_input)

st.write("---")

# 2. بخش اقلام سفارش
st.header("📦 اقلام سفارش")

if 'cart' not in st.session_state:
    st.session_state.cart = []

products_df = load_products()

if not products_df.empty:
    with st.expander("افزودن کالا به لیست", expanded=True):
        p_col1, p_col2 = st.columns(2)
        with p_col1:
            # استفاده از نام‌های اصلاح شده ستون‌ها
            product_list = products_df["عنوان کالا"].tolist()
            selected_product_name = st.selectbox("انتخاب کالا:", product_list)
            selected_row = products_df[products_df["عنوان کالا"] == selected_product_name].iloc[0]
            product_code = selected_row["کد کالا"]
            st.info(f"کد کالا: {product_code}")
        with p_col2:
            weight = st.number_input("مقدار (کیلوگرم):", min_value=0.0, step=0.5, format="%.2f")
            price = st.number_input("فی (تومان):", min_value=0, step=1000)

        if st.button("➕ افزودن به فاکتور"):
            if weight > 0 and price > 0:
                item = {
                    "ProductCode": product_code,
                    "ProductName": selected_product_name,
                    "Weight": weight,
                    "UnitPrice": price,
                    "TotalPrice": weight * price
                }
                st.session_state.cart.append(item)
                st.toast("کالا به سبد اضافه شد")
            else:
                st.error("لطفا مقدار و فی را وارد کنید")

    if st.session_state.cart:
        st.subheader("پیش‌فاکتور")
        cart_df = pd.DataFrame(st.session_state.cart)
        st.table(cart_df[["ProductName", "Weight", "UnitPrice", "TotalPrice"]])
        
        total_invoice = cart_df["TotalPrice"].sum()
        st.metric("جمع کل (تومان)", f"{total_invoice:,.0f}")

        if st.button("✅ ثبت نهایی و صدور فاکتور", type="primary"):
            if not final_name or not address:
                st.error("اطلاعات مشتری (نام و آدرس) تکمیل نیست!")
            else:
                inv_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                inv_no = int(time.time())
                
                save_customer(final_name, address, phone, c_type)
                save_order(inv_no, inv_date, final_name, cart_df)
                
                st.balloons()
                st.success(f"فاکتور شماره {inv_no} با موفقیت ثبت شد.")
                
                with st.container():
                    st.markdown(f"""
                    ### فاکتور فروش
                    **شماره:** {inv_no}  |  **تاریخ:** {inv_date}  
                    **مشتری:** {final_name}  |  **تلفن:** {phone}  
                    **آدرس:** {address}
                    """)
                    st.dataframe(cart_df[["ProductName", "Weight", "TotalPrice"]], use_container_width=True)
                    st.write(f"**مبلغ قابل پرداخت: {total_invoice:,.0f} تومان**")
                
                st.session_state.cart = []
                if st.button("ثبت سفارش جدید"):
                    st.rerun()
    else:
        st.info("سبد خرید خالی است.")
else:
    st.error("فایل محصولات (products.csv) یافت نشد یا ستون‌های آن اشتباه است.")
