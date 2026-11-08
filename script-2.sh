# فحص رقم
phonex scan "+9647701234567" -o report.html

# تشغيل سيرفر الالتقاط
phonex serve --host 0.0.0.0 --port 8080

# طباعة روابط الالتقاط واللوحة لفحص معيّن
phonex link <scan_id>