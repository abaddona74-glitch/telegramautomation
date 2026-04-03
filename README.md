# Telegram Agent (Userbot) - Google Sheets Avtomatlashtirish

Bu loyiha Google Sheets yordamida Telegram orqali xabarlarni avtomatik tarzda (spam bloklarsiz, kunlik limitni inobatga olgan holda) tarqatuvchi **Userbot (Telethon)** hisoblanadi. Tizim sizning asl profilingiz yoki ochilgan maxsus agent profil nomidan ishlaydi, shuning uchun foydalanuvchilar akkauntga birinchi bo'lib yozishi (/start bosishi) shart emas.

##  Imkoniyatlari

- Muvaffaqiyatli jo'natilgan xabarlarni yozib borish (state.db orqali)  kompyuter/dastur qotib qolsa yoki o'chirib yoqilsa ham **kunlik limit buzilmaydi**.
- **Rate Limit & Delay:** Kunlik atch_size (jo'natishlar soni) to'lgach, qolgan foydalanuvchilarni avtomatik ravishda keyingi kunga (delayed) o'tkazib qo'yadi.
- Jo'natish vaqtini Google Sheets da Kalendar orqali qulay belgilash.
- Matnlar, Rasmlar va Fayllarni Markdown yoki HTML formatida yuborish.
- Raqam, username yoki chat_id orqali yuborishni to'liq qo'llab-quvvatlaydi.

---

##  O'rnatish (Installation)

### 1-Qadam: Dasturni o'rnatish va muhitni tayyorlash
Terminal (CMD/PowerShell) ni ochamiz va quyidagi komandalarni ketma-ket bajaramiz:

`powershell
# 1. Virtual muhit (venv) yaratish:
python -m venv .venv

# 2. Virtual muhitni faollashtirish (Windows uchun):
.venv\Scripts\activate

# 3. Kerakli modullarni o'rnatish:
pip install -r requirements.txt
`

---

### 2-Qadam: .env Faylini Sozlash (Konfiguratsiya)
Loyiha asosiy jildida (ochgan papkangizda) .env faylini yarating va uni quyidagi ma'lumotlar bilan to'ldiring:

`env
# -- TELEGRAM AGENT SOZLAMALARI --
# 1. my.telegram.org saytiga kirib "API development tools" dan quyidagi ma'lumotlarni olasiz:
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
# Session uchun ixtiyoriy nom (shu nomda .session fayli hosil bo'ladi)
TELEGRAM_SESSION_NAME=my_agent_session

# -- GOOGLE SHEETS SOZLAMALARI --
# 2. Google Cloud dagi Service Account JSON kalitining fayli manzili
GOOGLE_SERVICE_ACCOUNT_FILE=secrets/mysupporttbot-57b27007f0c3.json
# 3. Google Sheet faylingizning ochiq Manzili (URL linki) yoki fayl ID'si
GOOGLE_SHEET_URL=https://docs.google.com/spreadsheets/d/.../edit

# Google Sheet varaqlarining nomlanishi (ixtiyoriy, agar aynan shunday deyilgan bo'lsa tegmang)
CONTACTS_SHEET=contacts
TEMPLATES_SHEET=templates
SETTINGS_SHEET=settings

# -- TIZIM SOZLAMALARI --
TIMEZONE=Asia/Tashkent
SQLITE_PATH=runtime/state.db
POLL_INTERVAL_SECONDS=10
LOG_LEVEL=INFO

# Uskunani osonlikcha o'zgartirishlar:
ENABLE_AUTO_GRID_FORMAT=true
AUTO_GRID_CHECK_EVERY_CYCLES=6
ENABLE_CONTACTS_COMPACT=true
`

** Muhim:** Google Service Account (.json) dan oldingizdagi client_email ni o'zingizning brauzeringizdagi **Google Sheet** faylingizga (shaxsiy emailingiz kabi) **"Muharrir" (Editor)** sifatida qoshish esingizdan chiqmasin!

---

### 3-Qadam: Tizimga kirish (Birinchi marta avtorizatsiya)
Tizim aynan sizning yoki agentning profili (Userbot API) orqali yozishi uchun, dasturni asosiy yurgizishdan avval "Session" kalitini olish kerak.

Terminalda ushbu komandani tering:
`powershell
python -m telegramautomation.auth
`
- Dastur raqamingizni so'raydi, kiritasiz (masalan qolbola, +998901234567).
- Telegram ilovasiga kod keladi, shuni qaytarib yozasiz.
- Muvaffaqiyatli kirilsa, jildingizda my_agent_session.session (Siz .env da yozgan nom bilan) maxfiy fayl paydo bo'ladi. Dastur mana shu orqali profilni tanib ishlashda davom etadi. Xavfsizlik qoidalariga rioya qilib bu faylni hech kimga bermagin!

---

### 4-Qadam: Dasturni Ishga Tushirish
Muhit tayyor. Hamma sozlamalar bitdi! Endi agentni to'liq quvvat bilan ishga solamiz:

`powershell
python -m telegramautomation
`

**Dastur qanday ishlaydi?**
1. **Google Sheets** varag'iga qarab turadi.
2. contacts varag'idagi navbatdagi qatorlarni yuklaydi, jo'natilishi kerak bo'lganlarga SMS tashlaydi.
3. Kunning kvotasi qancha (atch_size=50) va xabarlar orasida vaqt qancha pauza qilinishi (min_delay_seconds=60) Google Sheet dagi settings varag'ida belgilanadi.
4. Vaqti tugagan va limit ro'yxatni ertangi sanaga surib (delayed status bn) uzida belgilab o'tib ketadi. Limit ertasi kungi kalendar kuniga o'tganda yana avtomatik ochilib beriladi.

Dasturni to'xtatish uchun terminalda Ctrl+C ni bosing.
