FROM python:3.9-slim

WORKDIR /app

# نصب کتابخانه‌های پایتون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی کردن کد برنامه
COPY . .

# پورت استریم‌لیت
EXPOSE 8501

# دستور اجرا
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
