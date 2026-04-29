import streamlit as st
import pandas as pd
import os
import time
import jdatetime  # اضافه شدن کتابخانه تاریخ شمسی

# --- تنظیمات صفحه ---
st.set_page_config(page_title="سیستم پخش مویرگی", layout="centered", page_icon="🚛")

# ==========================================
# --- سیستم احراز هویت (Login) ---
# ==========================================
USERS = {
    "admin": "admin123@",
    "amir": "04700"
}

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

def login_form():
    st.title("🔐 ورود به سامانه ویزیتور")
    st.write("لطفا نام کاربری و رمز عبور خود را وارد کنید.")
    with st.form("login_form"):
        username = st.text_input("نام کاربری")
        password = st.text_input("رمز عبور", type="password")
        submit = st.form_submit_button("ورود")
        
        if submit:
            if username in USERS and USERS[username] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("نام کاربری یا رمز عبور اشتباه است!")

# اگر کاربر لاگین نکرده، فرم ورود را نشان بده و بقیه کد را متوقف کن
if not st.session_state.logged_in:
    login_form()
    st.stop()

# ==========================================
# --- توابع دیتابیس و فایل‌ها ---
# ==========================================
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
        
        df = pd.read_csv(PRODUCT_FILE).dropna(how='all')
        
        if len(df.columns) >= 2:
            new_cols = list(df.columns)
            new_cols[0] = "کد کالا"
            new_cols[1] = "عنوان کالا"
            df.columns = new_cols
        
        df = df.astype(str)
        for col in df.columns:
            df[col] = df[col].str.strip().str.replace('ك', 'ک').str.replace('ي', 'ی')
            
        return df
    except Exception as e:
        st.error(f"خطا در بارگذاری لیست کالاها: {e}")
        return pd.DataFrame()

def load_customers():
    if os.path.exists(CUSTOMERS_DB):
        try:
            return pd.read_csv(CUSTOMERS_DB, on_bad_lines='skip')
        except:
            return pd.DataFrame(columns=["Name", "Address", "Phone", "Type"])
    else:
        return pd.DataFrame(columns=["Name", "Address", "Phone", "Type"])

def save_customer(name, address, phone, c_type):
    df = load_customers()
    # اصلاح کاراکترهای عربی و حذف کاما برای جلوگیری از خرابی CSV
    name = name.strip().replace('ك', 'ک').replace('ي', 'ی').replace(',', '،')
    address = address.replace(',', '،')
    
    if not df.empty and name in df["Name"].values:
        df.loc[df["Name"] == name, ["Address", "Phone", "Type"]] = [address, phone, c_type]
    else:
        new_row = pd.DataFrame({"Name": [name], "Address": [address], "Phone": [phone], "Type": [c_type]})
        df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(CUSTOMERS_DB, index=False)

def save_order(invoice_no, date, customer_name, items_df, issuer, sale_type):
    to_save = items_df.copy()
    # اصلاح متن‌ها برای جلوگیری از تداخل با جداکننده CSV
    customer_name = customer_name.replace(',', '،')
    if "ProductName" in to_save.columns:
        to_save["ProductName"] = to_save["ProductName"].astype(str).str.replace(',', '،')
    
    to_save["InvoiceNo"] = invoice_no
    to_save["Date"] = date
    to_save["Customer"] = customer_name
    to_save["SaleType"] = sale_type  # <--- اضافه شدن نوع فروش
    to_save["Issuer"] = issuer  # ثبت کننده فاکتور
    
    if not os.path.exists(ORDERS_DB):
        to_save.to_csv(ORDERS_DB, index=False)
    else:
        to_save.to_csv(ORDERS_DB, mode='a', header=False, index=False)

# ==========================================
# --- رابط کاربری اصلی (پس از لاگین) ---
# ==========================================

# نوار کناری (Sidebar) برای خروج و اطلاعات کاربر
st.sidebar.title("پنل کاربری")
st.sidebar.success(f"👤 کاربر فعال: **{st.session_state.username}**")
if st.sidebar.button("🚪 خروج از حساب"):
    st.session_state.logged_in = False
    st.session_state.username = None
    st.rerun()

st.title("🚛 سامانه پخش مویرگی")
st.write("---")

# ساخت دو تب مجزا
tab1, tab2 = st.tabs(["🛒 ثبت سفارش جدید", "📄 فاکتورهای صادر شده"])

# ------------------------------------------
# تب اول: ثبت سفارش
# ------------------------------------------
with tab1:
    st.header("👤 مشخصات مشتری")

    customers_df = load_customers()
    existing_names = customers_df["Name"].tolist() if not customers_df.empty else []

    search_mode = st.radio("وضعیت مشتری:", ["مشتری جدید", "جستجوی مشتری قدیم"], horizontal=True)

    name_input, address_input, phone_input, type_input = "", "", "", "نانوایی"

    if search_mode == "جستجوی مشتری قدیم" and existing_names:
        selected_name = st.selectbox("نام مشتری را انتخاب کنید:", [""] + existing_names)
        if selected_name:
            cust_data = customers_df[customers_df["Name"] == selected_name].iloc[0]
            name_input, address_input, phone_input, type_input = selected_name, cust_data["Address"], cust_data["Phone"], cust_data["Type"]
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
    st.header("📦 اقلام سفارش")

    if 'cart' not in st.session_state:
        st.session_state.cart = []

    products_df = load_products()

    if not products_df.empty:
        with st.expander("افزودن کالا به لیست", expanded=True):
            p_col1, p_col2 = st.columns(2)
            with p_col1:
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
            
            # جدا کردن سه رقم سه رقم برای نمایش در جدول
            display_cart = cart_df[["ProductName", "Weight", "UnitPrice", "TotalPrice"]].copy()
            display_cart.rename(columns={"ProductName": "نام کالا", "Weight": "مقدار", "UnitPrice": "فی (تومان)", "TotalPrice": "جمع (تومان)"}, inplace=True)
            display_cart["فی (تومان)"] = display_cart["فی (تومان)"].apply(lambda x: f"{x:,.0f}")
            display_cart["جمع (تومان)"] = display_cart["جمع (تومان)"].apply(lambda x: f"{x:,.0f}")
            
            st.table(display_cart)
            
            total_invoice = cart_df["TotalPrice"].sum()
            st.metric("جمع کل (تومان)", f"{total_invoice:,.0f}")

            st.write("---")
            # اضافه شدن انتخاب نوع فروش
            sale_type = st.radio("نوع فروش:", ["نقدی", "اعتباری", "چکی"], horizontal=True)

            if st.button("✅ ثبت نهایی و صدور فاکتور", type="primary"):
                if not final_name or not address:
                    st.error("اطلاعات مشتری (نام و آدرس) تکمیل نیست!")
                else:
                    # تولید تاریخ شمسی
                    inv_date = jdatetime.datetime.now().strftime("%Y/%m/%d %H:%M")
                    inv_no = int(time.time())
                    
                    save_customer(final_name, address, phone, c_type)
                    # ارسال نام کاربری و نوع فروش به عنوان ثبت کننده فاکتور
                    save_order(inv_no, inv_date, final_name, cart_df, st.session_state.username, sale_type)
                    
                    st.success(f"فاکتور شماره {inv_no} با موفقیت ثبت شد.")
                    
                    with st.container():
                        st.markdown(f"""
                        ### فاکتور فروش
                        **شماره:** {inv_no}  |  **تاریخ:** {inv_date}  |  **ثبت کننده:** {st.session_state.username}
                        **نوع فروش:** {sale_type}
                        **مشتری:** {final_name}  |  **تلفن:** {phone}  
                        **آدرس:** {address}
                        """)
                        st.table(display_cart[["نام کالا", "مقدار", "جمع (تومان)"]])
                        st.write(f"**مبلغ قابل پرداخت: {total_invoice:,.0f} تومان**")
                    
                    st.session_state.cart = []
        else:
            st.info("سبد خرید خالی است.")
    else:
        st.error("فایل محصولات یافت نشد یا ساختار آن (ستون ۱ و ۲) اشتباه است.")


# ------------------------------------------
# تب دوم: گزارش فاکتورهای صادر شده
# ------------------------------------------
with tab2:
    st.header("📄 لیست فاکتورهای صادر شده")
    
    if os.path.exists(ORDERS_DB):
        try:
            # استفاده از on_bad_lines برای جلوگیری از کرش کردن در صورت خرابی فایل
            orders_df = pd.read_csv(ORDERS_DB, on_bad_lines='skip')
            if not orders_df.empty:
                display_orders = orders_df.copy()
                
                # تبدیل مقادیر به عدد و فرمت سه رقم سه رقم
                for col in ["UnitPrice", "TotalPrice"]:
                    if col in display_orders.columns:
                        display_orders[col] = pd.to_numeric(display_orders[col], errors='coerce')
                        display_orders[col] = display_orders[col].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "")
                
                # ترجمه و مرتب‌سازی ستون‌ها برای نمایش زیبا (اضافه شدن نوع فروش)
                cols_to_show = {
                    "InvoiceNo": "شماره فاکتور",
                    "Date": "تاریخ",
                    "Customer": "مشتری",
                    "SaleType": "نوع فروش",  # <--- ستون جدید
                    "ProductName": "نام کالا",
                    "Weight": "مقدار",
                    "UnitPrice": "فی (تومان)",
                    "TotalPrice": "جمع کل (تومان)",
                    "Issuer": "ثبت کننده"
                }
                
                display_orders = display_orders[[c for c in cols_to_show.keys() if c in display_orders.columns]]
                display_orders.rename(columns=cols_to_show, inplace=True)
                
                st.dataframe(display_orders, use_container_width=True, hide_index=True)
                
            else:
                st.info("فایلی وجود دارد اما فاکتوری درون آن ثبت نشده است.")
        except Exception as e:
            st.error(f"خطا در خواندن فایل فاکتورها: {e}")
    else:
        st.info("هنوز هیچ فاکتوری صادر نشده است.")
