# Telegram Agent (Userbot) — Google Sheets Avtomatlashtirish

Bu loyiha **Telethon Userbot** asosida ishlaydi va Google Sheets orqali Telegram xabarlarini avtomatik yuboradi. Tizim kunlik limitlarni saqlaydi, kechiktirish (delay) qoidalariga amal qiladi va to‘xtab qolgan holatda ham davomiylikni buzmaydi.

## Imkoniyatlar

- Jo‘natilgan xabarlar holatini `state.db` da saqlash
- Kunlik limit (`batch_size`) to‘lganda avtomatik keyingi kunga surish (`delayed`)
- Google Sheets orqali yuborish vaqtini qulay boshqarish
- Matn, rasm va fayllarni yuborish (Markdown/HTML)
- Qabul qiluvchini `raqam`, `username` yoki `chat_id` orqali aniqlash

---

## O‘rnatish (Installation)

### 1) Virtual muhit va kutubxonalar

```powershell
# 1. Virtual muhit yaratish
python -m venv .venv

# 2. Virtual muhitni faollashtirish (Windows)
.venv\Scripts\activate

# 3. Kerakli paketlarni o‘rnatish
pip install -r requirements.txt
```

---

### 2) `.env` faylni sozlash

Loyiha ildizida `.env` fayl yarating va quyidagini kiriting:

```env
# -- TELEGRAM AGENT SOZLAMALARI --
# my.telegram.org -> API development tools
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_SESSION_NAME=my_agent_session

# -- GOOGLE SHEETS SOZLAMALARI --
GOOGLE_SERVICE_ACCOUNT_FILE=secrets/mysupporttbot-57b27007f0c3.json
GOOGLE_SHEET_URL=https://docs.google.com/spreadsheets/d/.../edit

# Varaq nomlari
CONTACTS_SHEET=contacts
TEMPLATES_SHEET=templates
SETTINGS_SHEET=settings

# -- TIZIM SOZLAMALARI --
TIMEZONE=Asia/Tashkent
SQLITE_PATH=runtime/state.db
POLL_INTERVAL_SECONDS=10
LOG_LEVEL=INFO

# Qo‘shimcha sozlamalar
ENABLE_AUTO_GRID_FORMAT=true
AUTO_GRID_CHECK_EVERY_CYCLES=6
ENABLE_CONTACTS_COMPACT=true
```

> **Muhim:** Service Account JSON ichidagi `client_email` ni Google Sheet’ga **Editor** huquqi bilan qo‘shing.

---

### 3) Birinchi marta avtorizatsiya (session yaratish)

```powershell
python -m telegramautomation.auth
```

- Telefon raqamingizni kiriting
- Telegram’dan kelgan kodni kiriting
- Muvaffaqiyatli bo‘lsa, `.env` dagi nom bilan `.session` fayl yaratiladi

---

### 4) Dasturni ishga tushirish

```powershell
python -m telegramautomation
```

## Ishlash tartibi

1. Dastur Google Sheets’ni doimiy kuzatadi
2. `contacts` varaqdagi navbatdagi yozuvlarga xabar yuboradi
3. `settings` varaqdagi limit va delay bo‘yicha ishlaydi
4. Limit tugasa qolgan yozuvlarni keyingi kunga o‘tkazadi

Dasturdan chiqish: **Ctrl + C**

---

## Foydali havolalar

- Telegram API: [LINK](https://my.telegram.org)
- Google Sheets: [LINK](https://docs.google.com/spreadsheets)
