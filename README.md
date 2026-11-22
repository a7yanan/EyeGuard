# EyeGuard

يحمي عينك من ضوء الشاشة (فلتر ألوان دافئ + تذكير بتحريك العين).

## التشغيل من المصدر
```bat
run.bat
```

## بناء ملف تنفيذي
```bat
build.bat
```
ينتج:
- `dist\EyeGuard.exe` — البرنامج
- `dist\EyeGuard_Setup.exe` — المثبت

## التحديث التلقائي (GitHub Releases)

1. أنشئ مستودعاً على GitHub (مثلاً `3omar_a7yanan/EyeGuard`).
2. في `eyeguard.py` عدّل إن لزم:
   ```python
   GITHUB_REPO = "3omar_a7yanan/EyeGuard"
   UPDATE_ASSET = "EyeGuard.exe"
   ```
3. ارفع الكود (مجلد `v1` أو محتواه).
4. عند كل إصدار جديد:
   - زِد `APP_VERSION` (الحالي `1` → يظهر **v1**؛ بعده مثلاً `1.1` أو `2`)
   - ابنِ `EyeGuard.exe` بـ `build.bat`
   - من GitHub → **Releases** → **Create a new release**
   - **Tag**: `v1` (أو `v1.1` / `v2` بنفس رقم `APP_VERSION`)
   - ارفع المرفق **`EyeGuard.exe`**
5. البرنامج يتحقق تلقائياً مرة كل يوم، ومن **آخر الإعدادات**: **البحث عن تحديث**.

> التحديث يستبدل `EyeGuard.exe` فقط عندما يعمل من النسخة المبنية (ليس من `python eyeguard.py`).

## المتطلبات
- Windows 10/11
- Python 3 + Pillow (للتطوير والبناء)
