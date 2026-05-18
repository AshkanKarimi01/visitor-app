import streamlit as st
import pandas as pd
import os
import time
import io
import logging
import traceback
import jdatetime
from datetime import datetime
from zoneinfo import ZoneInfo

# --- تنظیمات لاگینگ ---
LOG_DIR = "data"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "app.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)

def log_action(level: str, message: str, user: str = "system"):
    full_msg = f"[{user}] {message}"
    if level == "INFO":
        logger.info(full_msg)
    elif level == "WARNING":
        logger.warning(full_msg)
    elif level == "ERROR":
        logger.error(full_msg)

# --- تنظیمات صفحه ---
st.set_page_config(
    page_title="سیستم پخش مویرگی",
    layout="wide",
    page_icon="🚛",
    initial_sidebar_state="collapsed"  # سایدبار در ابتدا بسته باشد
)

# --- CSS ساده (فقط RTL و فونت) ---
st.markdown("""
<style>
    body { direction: rtl; font-family: 'Vazir', sans-serif; }
    .stTextInput > label, .stSelectbox > label,
    .stTextArea > label, .stNumberInput > label,
    .stRadio > label { text-align: right; }
    .stAlert { text-align: right; }
    div[data-testid="stMetricValue"] { font-size: 1.5rem; }
    .stTabs [data-baseweb="tab"] { font-size: 1rem; }
    .stApp { direction: rtl; }
    /* حذف هرگونه استایل اضافی سایدبار */
    section[data-testid="stSidebar"] {
        display: none !important;
    }
    .main {
        margin-right: 0 !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# --- سیستم احراز هویت ---
# ==========================================
USERS = {
    "admin": {"password": "admin123@", "role": "admin"},
    "amir":  {"password": "04700",     "role": "user"},
}

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'role' not in st.session_state:
    st.session_state.role = None

def login_form():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 ورود به سامانه ویزیتور")
        st.write("لطفا نام کاربری و رمز عبور خود را وارد کنید.")
        with st.form("login_form"):
            username = st.text_input("نام کاربری")
            password = st.text_input("رمز عبور", type="password")
            submit = st.form_submit_button("ورود", use_container_width=True, type="primary")
            if submit:
                if username in USERS and USERS[username]["password"] == password:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.role = USERS[username]["role"]
                    log_action("INFO", "ورود موفق به سیستم", username)
                    st.rerun()
                else:
                    log_action("WARNING", f"تلاش ناموفق برای ورود با نام کاربری: {username}", "anonymous")
                    st.error("نام کاربری یا رمز عبور اشتباه است!")

if not st.session_state.logged_in:
    login_form()
    st.stop()

# ==========================================
# --- مسیرهای فایل‌ها ---
# ==========================================
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

CUSTOMERS_DB = os.path.join(DATA_DIR, "customers_db.csv")
ORDERS_DB    = os.path.join(DATA_DIR, "orders_db.csv")
PRODUCT_FILE = "products.csv"
LOGO_FILE    = "logo.png"
PRICE_FILE   = "Book1.xlsx"

# ==========================================
# --- بارگذاری قیمت‌ها از فایل اکسل ---
# ==========================================
@st.cache_data(ttl=3600)
def load_price_mapping():
    if not os.path.exists(PRICE_FILE):
        st.warning(f"فایل {PRICE_FILE} یافت نشد. لطفاً آن را در کنار برنامه قرار دهید.")
        return {}
    try:
        df_price = pd.read_excel(PRICE_FILE, sheet_name="IB01", dtype=str)
        code_col = None
        price_col = None
        for col in df_price.columns:
            if "كد كالا" in col or "کد کالا" in col:
                code_col = col
            if "فی صادره" in col:
                price_col = col
        if code_col is None or price_col is None:
            st.error("ستون‌های مورد نیاز (كد كالا و فی صادره) در فایل اکسل یافت نشد.")
            return {}
        df_price = df_price.dropna(subset=[code_col, price_col])
        mapping = {}
        for _, row in df_price.iterrows():
            code = str(row[code_col]).strip()
            price_str = str(row[price_col]).strip()
            try:
                price = int(price_str.replace(',', '').replace('،', ''))
                mapping[code] = price
            except:
                continue
        return mapping
    except Exception as e:
        log_action("ERROR", f"خطا در خواندن فایل قیمت: {e}")
        st.error(f"خطا در خواندن {PRICE_FILE}: {e}")
        return {}

# ==========================================
# --- توابع PDF ---
# ==========================================
def _download_font(url, dest):
    if os.path.exists(dest):
        return True
    try:
        import requests
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        r = requests.get(url, stream=True, timeout=30)
        if r.status_code == 200:
            with open(dest, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        else:
            return False
    except Exception as e:
        log_action("ERROR", f"خطا در دانلود فونت: {e}")
        return False

def _reshape_persian(text: str) -> str:
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except ImportError:
        log_action("WARNING", "کتابخانه arabic_reshaper یا python-bidi نصب نیست.")
        return text

def generate_invoice_pdf(invoice_no, inv_date, customer_name, phone, address,
                         c_type, sale_type, issuer, cart_df, total_invoice) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                     Paragraph, Spacer, Image, HRFlowable)
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

    font_dir = "fonts"
    os.makedirs(font_dir, exist_ok=True)
    regular_font_path = os.path.join(font_dir, "Vazirmatn-Regular.ttf")
    bold_font_path    = os.path.join(font_dir, "Vazirmatn-Bold.ttf")

    regular_url = "https://github.com/rastikerdar/vazirmatn/releases/download/v33.003/Vazirmatn-Regular.ttf"
    bold_url    = "https://github.com/rastikerdar/vazirmatn/releases/download/v33.003/Vazirmatn-Bold.ttf"

    if not os.path.exists(regular_font_path):
        _download_font(regular_url, regular_font_path)
    if not os.path.exists(bold_font_path):
        _download_font(bold_url, bold_font_path)

    FONT_NAME = "Helvetica"
    FONT_BOLD = "Helvetica-Bold"
    try:
        if os.path.exists(regular_font_path):
            pdfmetrics.registerFont(TTFont("Vazir", regular_font_path))
            FONT_NAME = "Vazir"
        if os.path.exists(bold_font_path):
            pdfmetrics.registerFont(TTFont("Vazir-Bold", bold_font_path))
            FONT_BOLD = "Vazir-Bold"
    except Exception as e:
        log_action("ERROR", f"خطا در ثبت فونت: {e}")

    def P(text, size=10, bold=False, align=TA_RIGHT, color=colors.black):
        fn = FONT_BOLD if bold else FONT_NAME
        style = ParagraphStyle(
            name=f"s{size}{bold}{align}",
            fontName=fn,
            fontSize=size,
            textColor=color,
            alignment=align,
            leading=size * 1.5,
            wordWrap='RTL' if FONT_NAME != "Helvetica" else 'LTR',
        )
        return Paragraph(_reshape_persian(str(text)), style)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
    story = []

    # هدر
    logo_cell = ""
    if os.path.exists(LOGO_FILE):
        try:
            logo_img = Image(LOGO_FILE, width=3*cm, height=3*cm)
            logo_cell = logo_img
        except:
            logo_cell = P("🚛", 20, align=TA_CENTER)
    else:
        logo_cell = P("🚛", 20, align=TA_CENTER)

    title_content = [
        P("فاکتور فروش", 18, bold=True, align=TA_CENTER, color=colors.HexColor("#1a5276")),
        P("سامانه پخش مویرگی", 11, align=TA_CENTER, color=colors.HexColor("#555555")),
    ]
    header_table = Table([[logo_cell, title_content, ""]], colWidths=[3*cm, None, 3*cm])
    header_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                                      ('ALIGN', (0,0), (0,0), 'CENTER'),
                                      ('ALIGN', (1,0), (1,0), 'CENTER'),
                                      ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
    story.append(header_table)
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a5276")))
    story.append(Spacer(1, 0.3*cm))

    # اطلاعات فاکتور
    inv_info = [
        [P(f"شماره فاکتور: {invoice_no}", 9, bold=True), P(f"تاریخ: {inv_date}", 9, bold=True)],
        [P(f"ثبت کننده: {issuer}", 9), P(f"نوع فروش: {sale_type}", 9)],
    ]
    inv_table = Table(inv_info, colWidths=[None, None])
    inv_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#d6eaf8")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#aed6f1")),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.HexColor("#eaf4fb"), colors.white]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(inv_table)
    story.append(Spacer(1, 0.3*cm))

    # اطلاعات مشتری
    story.append(P("اطلاعات مشتری", 12, bold=True, color=colors.HexColor("#1a5276")))
    story.append(Spacer(1, 0.2*cm))
    cust_info = [
        [P(f"نام مشتری: {customer_name}", 10, bold=True), P(f"صنف: {c_type}", 10)],
        [P(f"تلفن: {phone}", 10), P(f"آدرس: {address}", 10)],
    ]
    cust_table = Table(cust_info, colWidths=[None, None])
    cust_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#aed6f1")),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.HexColor("#fdfefe"), colors.HexColor("#f4f6f7")]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(cust_table)
    story.append(Spacer(1, 0.4*cm))

    # جدول اقلام
    story.append(P("اقلام سفارش", 12, bold=True, color=colors.HexColor("#1a5276")))
    story.append(Spacer(1, 0.2*cm))
    items_header = [
        P("ردیف", 10, bold=True, align=TA_CENTER),
        P("کد کالا", 10, bold=True, align=TA_CENTER),
        P("نام کالا", 10, bold=True, align=TA_CENTER),
        P("مقدار (کگ)", 10, bold=True, align=TA_CENTER),
        P("فی (ریال)", 10, bold=True, align=TA_CENTER),
        P("جمع (ریال)", 10, bold=True, align=TA_CENTER),
    ]
    items_data = [items_header]
    for i, row in cart_df.iterrows():
        items_data.append([
            P(str(i+1), 9, align=TA_CENTER),
            P(str(row.get("ProductCode", "-")), 8, align=TA_CENTER),
            P(str(row.get("ProductName", "-")), 9, align=TA_CENTER),
            P(f"{float(row.get('Weight',0)):,.1f}", 9, align=TA_CENTER),
            P(f"{float(row.get('UnitPrice',0)):,.0f}", 9, align=TA_CENTER),
            P(f"{float(row.get('TotalPrice',0)):,.0f}", 9, align=TA_CENTER),
        ])
    items_data.append([
        P("",9), P("",9), P("",9), P("",9),
        P("جمع کل:", 10, bold=True, align=TA_CENTER),
        P(f"{total_invoice:,.0f} ریال", 10, bold=True, align=TA_CENTER, color=colors.HexColor("#c0392b")),
    ])
    col_w = [1*cm, 3.2*cm, None, 2*cm, 2.5*cm, 3*cm]
    items_table = Table(items_data, colWidths=col_w, repeatRows=1)
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1a5276")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-2), 0.5, colors.HexColor("#aed6f1")),
        ('LINEABOVE', (0,-1), (-1,-1), 1.5, colors.HexColor("#1a5276")),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, colors.HexColor("#eaf4fb")]),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#d5f5e3")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 0.5*cm))

    # امضا و footer
    sign_data = [[P("مهر و امضای فروشنده:", 9, align=TA_CENTER), P("",9), P("امضای خریدار:", 9, align=TA_CENTER)]]
    sign_table = Table(sign_data, colWidths=[None, 2*cm, None])
    sign_table.setStyle(TableStyle([
        ('BOX', (0,0), (0,0), 0.5, colors.grey),
        ('BOX', (2,0), (2,0), 0.5, colors.grey),
        ('MINROWHEIGHT', (0,0), (-1,-1), 2*cm),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(sign_table)
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(P("این فاکتور به صورت سیستمی صادر شده و فاقد امضا معتبر نمی‌باشد.", 8, align=TA_CENTER, color=colors.grey))

    doc.build(story)
    return buf.getvalue()

# ==========================================
# --- توابع دیتابیس ---
# ==========================================
@st.cache_data(ttl=60)
def load_products():
    try:
        if not os.path.exists(PRODUCT_FILE):
            return pd.DataFrame(columns=["کد کالا", "عنوان کالا"])
        df = pd.read_csv(PRODUCT_FILE).dropna(how='all')
        if len(df.columns) >= 2:
            cols = list(df.columns)
            cols[0] = "کد کالا"
            cols[1] = "عنوان کالا"
            df.columns = cols
        df = df.astype(str)
        for col in df.columns:
            df[col] = df[col].str.strip().str.replace('ك', 'ک').str.replace('ي', 'ی')
        return df
    except Exception as e:
        log_action("ERROR", f"خطا در بارگذاری محصولات: {e}")
        return pd.DataFrame(columns=["کد کالا", "عنوان کالا"])

def load_customers():
    if os.path.exists(CUSTOMERS_DB):
        try:
            df = pd.read_csv(CUSTOMERS_DB, on_bad_lines='skip')
            for col in ["Name", "Address", "Phone", "Type"]:
                if col not in df.columns:
                    df[col] = ""
            return df
        except Exception as e:
            log_action("ERROR", f"خطا در بارگذاری مشتریان: {e}")
            return pd.DataFrame(columns=["Name", "Address", "Phone", "Type"])
    return pd.DataFrame(columns=["Name", "Address", "Phone", "Type"])

def save_customer(name, address, phone, c_type, user="system"):
    try:
        df = load_customers()
        name    = name.strip().replace('ك', 'ک').replace('ي', 'ی').replace(',', '،')
        address = address.replace(',', '،')
        phone   = str(phone).strip()
        is_new = df.empty or name not in df["Name"].values
        if not is_new:
            df.loc[df["Name"] == name, ["Address", "Phone", "Type"]] = [address, phone, c_type]
            log_action("INFO", f"اطلاعات مشتری بروزرسانی شد: {name}", user)
        else:
            new_row = pd.DataFrame({"Name": [name], "Address": [address],
                                    "Phone": [phone], "Type": [c_type]})
            df = pd.concat([df, new_row], ignore_index=True)
            log_action("INFO", f"مشتری جدید ثبت شد: {name}", user)
        df.to_csv(CUSTOMERS_DB, index=False, encoding='utf-8-sig')
        return True
    except Exception as e:
        log_action("ERROR", f"خطا در ذخیره مشتری {name}: {e}")
        return False

def save_order(invoice_no, date, customer_name, items_df, issuer, sale_type):
    try:
        to_save = items_df.copy()
        customer_name = str(customer_name).replace(',', '،')
        if "ProductName" in to_save.columns:
            to_save["ProductName"] = to_save["ProductName"].astype(str).str.replace(',', '،')
        to_save["InvoiceNo"] = invoice_no
        to_save["Date"]      = date
        to_save["Customer"]  = customer_name
        to_save["SaleType"]  = sale_type
        to_save["Issuer"]    = issuer
        if not os.path.exists(ORDERS_DB):
            to_save.to_csv(ORDERS_DB, index=False, encoding='utf-8-sig')
        else:
            to_save.to_csv(ORDERS_DB, mode='a', header=False, index=False, encoding='utf-8-sig')
        log_action("INFO", f"فاکتور {invoice_no} برای مشتری {customer_name} ثبت شد - نوع: {sale_type}", issuer)
        return True
    except Exception as e:
        log_action("ERROR", f"خطا در ذخیره سفارش: {e}")
        return False

def load_orders():
    if not os.path.exists(ORDERS_DB):
        return pd.DataFrame()
    try:
        df = pd.read_csv(ORDERS_DB, on_bad_lines='skip', encoding='utf-8-sig')
        return df
    except Exception:
        try:
            return pd.read_csv(ORDERS_DB, on_bad_lines='skip')
        except Exception as e:
            log_action("ERROR", f"خطا در خواندن سفارش‌ها: {e}")
            return pd.DataFrame()

# ==========================================
# --- هدر اطلاعات کاربر (جایگزین سایدبار) ---
# ==========================================
st.title("🚛 سامانه پخش مویرگی")

# نمایش اطلاعات کاربر و آمار در بالای صفحه
col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
with col1:
    st.success(f"👤 کاربر فعال: **{st.session_state.username}**  |  نقش: {'مدیر' if st.session_state.role == 'admin' else 'ویزیتور'}")
with col2:
    if st.button("🚪 خروج از حساب", use_container_width=True):
        log_action("INFO", "خروج از سیستم", st.session_state.username)
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
with col3:
    cust_count = len(load_customers())
    st.metric("مشتریان ثبت‌شده", cust_count)
with col4:
    orders_df_s = load_orders()
    order_count = orders_df_s["InvoiceNo"].nunique() if not orders_df_s.empty and "InvoiceNo" in orders_df_s.columns else 0
    st.metric("فاکتورهای صادره", order_count)

st.divider()

# ==========================================
# --- تب‌ها ---
# ==========================================
if st.session_state.role == "admin":
    tab1, tab2, tab3, tab4 = st.tabs([
        "🛒 ثبت سفارش جدید",
        "📄 فاکتورهای صادر شده",
        "📤 خروجی و گزارش",
        "🔒 لاگ سیستم (ادمین)"
    ])
else:
    tab1, tab2, tab3 = st.tabs([
        "🛒 ثبت سفارش جدید",
        "📄 فاکتورهای صادر شده",
        "📤 خروجی و گزارش",
    ])
    tab4 = None

price_mapping = load_price_mapping()

# ==========================================
# --- تب ۱: ثبت سفارش ---
# ==========================================
with tab1:
    st.header("👤 مشخصات مشتری")

    customers_df   = load_customers()
    existing_names = customers_df["Name"].tolist() if not customers_df.empty else []

    search_mode = st.radio(
        "وضعیت مشتری:",
        ["مشتری جدید", "جستجوی مشتری قدیم"],
        horizontal=True,
        key="search_mode"
    )

    name_input = address_input = phone_input = ""
    type_input = "نانوایی"

    if search_mode == "جستجوی مشتری قدیم":
        if existing_names:
            selected_name = st.selectbox("نام مشتری را انتخاب کنید:", [""] + existing_names)
            if selected_name:
                cust_data  = customers_df[customers_df["Name"] == selected_name].iloc[0]
                name_input    = selected_name
                address_input = str(cust_data.get("Address", ""))
                phone_input   = str(cust_data.get("Phone", ""))
                type_input    = str(cust_data.get("Type", "نانوایی"))
        else:
            st.warning("هنوز مشتری در دیتابیس ثبت نشده است.")

    col1, col2 = st.columns(2)
    with col1:
        is_disabled = (search_mode == "جستجوی مشتری قدیم" and name_input != "")
        final_name = st.text_input("نام و نام خانوادگی:", value=name_input, disabled=is_disabled)
        c_type_options = ["نانوایی", "کبابی", "سایر"]
        c_type_idx = c_type_options.index(type_input) if type_input in c_type_options else 0
        c_type = st.selectbox("صنف:", c_type_options, index=c_type_idx)
    with col2:
        phone = st.text_input("شماره تلفن:", value=phone_input)

    address = st.text_area("آدرس:", value=address_input)

    st.divider()
    st.header("📦 اقلام سفارش")

    if 'cart' not in st.session_state:
        st.session_state.cart = []

    products_df = load_products()

    if not products_df.empty:
        with st.expander("➕ افزودن کالا به فاکتور", expanded=True):
            p_col1, p_col2, p_col3 = st.columns([3, 2, 2])
            with p_col1:
                product_list = products_df["عنوان کالا"].tolist()
                selected_product_name = st.selectbox("انتخاب کالا:", product_list, key="sel_product")
                sel_row = products_df[products_df["عنوان کالا"] == selected_product_name].iloc[0]
                product_code = sel_row["کد کالا"]
                st.info(f"کد کالا: **{product_code}**")
                base_price = price_mapping.get(str(product_code).strip(), 0)
                if base_price == 0:
                    st.error("⚠️ محصول قیمت مصوب ندارد. امکان افزودن به فاکتور نیست.")
                else:
                    st.success(f"💰 قیمت مصوب: {base_price:,} ریال")
            with p_col2:
                weight = st.number_input("مقدار (کیلوگرم):", min_value=0.0, step=0.5, format="%.2f", key="inp_weight")
            with p_col3:
                st.number_input("فی (ریال):", value=int(base_price), disabled=True, key="inp_price_disabled")

            if st.button("➕ افزودن به فاکتور", use_container_width=True):
                if base_price == 0:
                    st.error("این کالا قیمت مصوب ندارد. لطفاً با مدیر سیستم تماس بگیرید.")
                elif weight <= 0:
                    st.error("لطفاً مقدار (کیلوگرم) را وارد کنید.")
                else:
                    item = {
                        "ProductCode": product_code,
                        "ProductName": selected_product_name,
                        "Weight": weight,
                        "UnitPrice": base_price,
                        "TotalPrice": weight * base_price,
                    }
                    st.session_state.cart.append(item)
                    st.toast("✅ کالا به فاکتور اضافه شد")

        if st.session_state.cart:
            st.subheader("📋 پیش‌فاکتور")
            cart_df = pd.DataFrame(st.session_state.cart)

            display_cart = cart_df[["ProductName", "Weight", "UnitPrice", "TotalPrice"]].copy()
            display_cart.rename(columns={
                "ProductName": "نام کالا",
                "Weight":      "مقدار (کگ)",
                "UnitPrice":   "فی (ریال)",
                "TotalPrice":  "جمع (ریال)"
            }, inplace=True)
            display_cart["فی (ریال)"]  = display_cart["فی (ریال)"].apply(lambda x: f"{x:,.0f}")
            display_cart["جمع (ریال)"] = display_cart["جمع (ریال)"].apply(lambda x: f"{x:,.0f}")

            st.dataframe(display_cart, use_container_width=True, hide_index=True)

            del_col1, del_col2 = st.columns([3, 1])
            with del_col1:
                del_idx = st.number_input("شماره ردیف برای حذف:", min_value=1,
                                          max_value=len(st.session_state.cart), step=1, value=1)
            with del_col2:
                if st.button("🗑️ حذف ردیف", use_container_width=True):
                    st.session_state.cart.pop(del_idx - 1)
                    st.rerun()

            total_invoice = cart_df["TotalPrice"].sum()
            st.metric("💰 جمع کل (ریال)", f"{total_invoice:,.0f}")

            st.divider()
            sale_type = st.radio("نوع فروش:", ["نقدی", "اعتباری", "چکی"], horizontal=True)

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                submit_btn = st.button("✅ ثبت نهایی و صدور فاکتور", type="primary", use_container_width=True)
            with col_btn2:
                if st.button("🗑️ پاک کردن کل سبد", use_container_width=True):
                    st.session_state.cart = []
                    st.rerun()

            if submit_btn:
                fn = final_name.strip() if final_name else ""
                if not fn or not address.strip():
                    st.error("اطلاعات مشتری (نام و آدرس) تکمیل نیست!")
                else:
                    tehran = ZoneInfo("Asia/Tehran")
                    now_tehran = datetime.now(tehran)
                    inv_date = jdatetime.datetime.fromgregorian(datetime=now_tehran).strftime("%Y/%m/%d %H:%M")
                    inv_no = int(time.time())

                    ok_cust = save_customer(fn, address, phone, c_type, st.session_state.username)
                    ok_order = save_order(inv_no, inv_date, fn, cart_df,
                                          st.session_state.username, sale_type)

                    if ok_cust and ok_order:
                        st.success(f"✅ فاکتور شماره **{inv_no}** با موفقیت ثبت شد.")

                        with st.container(border=True):
                            st.markdown(f"""
                            ### 🧾 فاکتور فروش
                            **شماره:** `{inv_no}` | **تاریخ:** `{inv_date}` | **ثبت کننده:** `{st.session_state.username}`
                            **نوع فروش:** `{sale_type}` | **صنف:** `{c_type}`
                            **مشتری:** `{fn}` | **تلفن:** `{phone}`
                            **آدرس:** `{address}`
                            """)
                            st.dataframe(display_cart, use_container_width=True, hide_index=True)
                            st.write(f"**💰 مبلغ قابل پرداخت: {total_invoice:,.0f} ریال**")

                        try:
                            pdf_bytes = generate_invoice_pdf(
                                inv_no, inv_date, fn, phone, address,
                                c_type, sale_type, st.session_state.username,
                                cart_df, total_invoice
                            )
                            st.download_button(
                                label="⬇️ دانلود فاکتور PDF",
                                data=pdf_bytes,
                                file_name=f"invoice_{inv_no}.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                            )
                        except Exception as e:
                            log_action("ERROR", f"خطا در تولید PDF فاکتور {inv_no}: {traceback.format_exc()}")
                            st.error(f"فاکتور ثبت شد اما خطا در تولید PDF: {str(e)}")

                        st.session_state.cart = []
                    else:
                        st.error("خطا در ذخیره‌سازی. لاگ را بررسی کنید.")
        else:
            st.info("📭 سبد خرید خالی است. کالا اضافه کنید.")
    else:
        st.error("❌ فایل محصولات (products.csv) یافت نشد یا فاقد ستون‌های کد و عنوان است.")

# ==========================================
# --- تب ۲: فاکتورهای صادرشده ---
# ==========================================
with tab2:
    st.header("📄 لیست فاکتورهای صادر شده")
    orders_df = load_orders()
    if orders_df.empty:
        st.info("هنوز هیچ فاکتوری صادر نشده است.")
    else:
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            if "Customer" in orders_df.columns:
                customers_list = ["همه"] + sorted(orders_df["Customer"].dropna().unique().tolist())
                filter_cust = st.selectbox("فیلتر مشتری:", customers_list, key="f_cust")
            else:
                filter_cust = "همه"
        with f_col2:
            if "SaleType" in orders_df.columns:
                sale_types = ["همه"] + sorted(orders_df["SaleType"].dropna().unique().tolist())
                filter_sale = st.selectbox("فیلتر نوع فروش:", sale_types, key="f_sale")
            else:
                filter_sale = "همه"
        with f_col3:
            if "Issuer" in orders_df.columns:
                issuers = ["همه"] + sorted(orders_df["Issuer"].dropna().unique().tolist())
                filter_issuer = st.selectbox("فیلتر ثبت کننده:", issuers, key="f_issuer")
            else:
                filter_issuer = "همه"

        filtered_df = orders_df.copy()
        if filter_cust != "همه" and "Customer" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Customer"] == filter_cust]
        if filter_sale != "همه" and "SaleType" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["SaleType"] == filter_sale]
        if filter_issuer != "همه" and "Issuer" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Issuer"] == filter_issuer]

        if not filtered_df.empty and "TotalPrice" in filtered_df.columns:
            total_val = pd.to_numeric(filtered_df["TotalPrice"], errors='coerce').sum()
            m1, m2, m3 = st.columns(3)
            m1.metric("تعداد ردیف‌ها", len(filtered_df))
            inv_count = filtered_df["InvoiceNo"].nunique() if "InvoiceNo" in filtered_df.columns else "-"
            m2.metric("تعداد فاکتورها", inv_count)
            m3.metric("مجموع فروش (ریال)", f"{total_val:,.0f}")

        st.divider()
        display_orders = filtered_df.copy()
        for col in ["UnitPrice", "TotalPrice"]:
            if col in display_orders.columns:
                display_orders[col] = pd.to_numeric(display_orders[col], errors='coerce')
                display_orders[col] = display_orders[col].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "")

        cols_map = {
            "InvoiceNo":   "شماره فاکتور",
            "Date":        "تاریخ",
            "Customer":    "مشتری",
            "SaleType":    "نوع فروش",
            "ProductName": "نام کالا",
            "Weight":      "مقدار (کگ)",
            "UnitPrice":   "فی (ریال)",
            "TotalPrice":  "جمع (ریال)",
            "Issuer":      "ثبت کننده",
        }
        existing_cols = [c for c in cols_map if c in display_orders.columns]
        display_orders = display_orders[existing_cols].rename(columns=cols_map)
        st.dataframe(display_orders, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("🖨️ چاپ مجدد فاکتور")
        if "InvoiceNo" in orders_df.columns:
            inv_list = sorted(orders_df["InvoiceNo"].dropna().unique().tolist(), reverse=True)
            sel_inv = st.selectbox("انتخاب شماره فاکتور برای دانلود PDF:", inv_list, key="reprint_inv")
            if st.button("📄 دانلود PDF این فاکتور", use_container_width=True):
                try:
                    inv_rows = orders_df[orders_df["InvoiceNo"] == sel_inv]
                    if not inv_rows.empty:
                        r0 = inv_rows.iloc[0]
                        pdf_bytes = generate_invoice_pdf(
                            invoice_no=r0.get("InvoiceNo", ""),
                            inv_date=r0.get("Date", ""),
                            customer_name=r0.get("Customer", ""),
                            phone=load_customers().set_index("Name").get("Phone", pd.Series()).get(r0.get("Customer",""), ""),
                            address=load_customers().set_index("Name").get("Address", pd.Series()).get(r0.get("Customer",""), ""),
                            c_type=load_customers().set_index("Name").get("Type", pd.Series()).get(r0.get("Customer",""), ""),
                            sale_type=r0.get("SaleType", ""),
                            issuer=r0.get("Issuer", ""),
                            cart_df=inv_rows[["ProductCode","ProductName","Weight","UnitPrice","TotalPrice"]].copy(),
                            total_invoice=pd.to_numeric(inv_rows["TotalPrice"], errors='coerce').sum()
                        )
                        st.download_button("⬇️ دانلود", data=pdf_bytes, file_name=f"invoice_{sel_inv}.pdf", mime="application/pdf", use_container_width=True)
                except Exception as e:
                    st.error(f"خطا در تولید PDF: {e}")
                    log_action("ERROR", f"خطا در چاپ مجدد فاکتور {sel_inv}: {traceback.format_exc()}")

# ==========================================
# --- تب ۳: خروجی و گزارش ---
# ==========================================
with tab3:
    st.header("📤 خروجی و گزارش")
    out_col1, out_col2 = st.columns(2)
    with out_col1:
        st.subheader("📊 خروجی فاکتورهای ثبت‌شده")
        orders_df_exp = load_orders()
        if not orders_df_exp.empty:
            csv_orders = orders_df_exp.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button("⬇️ دانلود فاکتورها (CSV)", data=csv_orders,
                               file_name=f"orders_export_{jdatetime.date.today().strftime('%Y%m%d')}.csv",
                               mime="text/csv", use_container_width=True)
            if "TotalPrice" in orders_df_exp.columns:
                total_all = pd.to_numeric(orders_df_exp["TotalPrice"], errors='coerce').sum()
                st.info(f"**مجموع کل فروش:** {total_all:,.0f} ریال")
            if "Customer" in orders_df_exp.columns and "TotalPrice" in orders_df_exp.columns:
                orders_df_exp["TotalPrice"] = pd.to_numeric(orders_df_exp["TotalPrice"], errors='coerce')
                chart_data = orders_df_exp.groupby("Customer")["TotalPrice"].sum().sort_values(ascending=False).head(10)
                st.bar_chart(chart_data)
        else:
            st.info("هیچ فاکتوری ثبت نشده است.")
    with out_col2:
        st.subheader("👥 خروجی لیست مشتریان")
        customers_exp = load_customers()
        if not customers_exp.empty:
            csv_custs = customers_exp.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button("⬇️ دانلود لیست مشتریان (CSV)", data=csv_custs,
                               file_name=f"customers_export_{jdatetime.date.today().strftime('%Y%m%d')}.csv",
                               mime="text/csv", use_container_width=True)
            st.dataframe(customers_exp.rename(columns={"Name":"نام","Address":"آدرس","Phone":"تلفن","Type":"صنف"}),
                         use_container_width=True, hide_index=True)
        else:
            st.info("هنوز مشتری ثبت نشده است.")

# ==========================================
# --- تب ۴: لاگ سیستم ---
# ==========================================
if tab4 is not None:
    with tab4:
        st.header("🔒 لاگ سیستم")
        st.warning("⚠️ این بخش فقط برای مدیر سیستم قابل مشاهده است.")
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                log_content = f.read()
            lines = log_content.strip().split("\n")
            n_lines = st.slider("تعداد خطوط نمایش:", 20, min(500, len(lines)), 100)
            level_filter = st.multiselect("فیلتر سطح:", ["INFO", "WARNING", "ERROR"], default=["INFO", "WARNING", "ERROR"])
            filtered_lines = [l for l in lines if any(lv in l for lv in level_filter)]
            display_log = "\n".join(filtered_lines[-n_lines:])
            st.code(display_log, language=None)
            st.download_button("⬇️ دانلود فایل لاگ کامل", data=log_content.encode('utf-8'),
                               file_name=f"app_log_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                               mime="text/plain", use_container_width=True)
            if st.button("🗑️ پاک کردن لاگ", type="secondary"):
                with open(LOG_FILE, "w", encoding="utf-8") as f:
                    f.write("")
                log_action("WARNING", "فایل لاگ توسط ادمین پاک شد", st.session_state.username)
                st.success("لاگ پاک شد.")
                st.rerun()
        else:
            st.info("فایل لاگ هنوز ایجاد نشده است.")
