# Telegram Automation Agent

Google Sheets bilan integratsiyalangan Telegram yuborish agenti.

## Nima qiladi

- `contacts` sheet dan username/phone/chat_id bo'yicha kontaktlarni oladi.
- `templates` sheet dan matn/file shablonlarini oladi.
- Sozlanadigan limit (`batch_size`, `interval_hours`) bilan yuboradi.
- Limitdan oshganlarni keyingi oynaga (`delayed`) o'tkazadi.
- Yuborish statusini Sheets ga qayta yozadi (`state`, `sent_at`, `last_error`, `message_id`, `attempts`).

## Muhim Telegram cheklovi

Bot username ga yozishi uchun user avval botni `start` qilgan bo'lishi kerak.
Phone orqali to'g'ridan-to'g'ri yuborish bot API da kafolatlanmagan; `chat_id` ustuni mavjud bo'lsa yuborish aniq ishlaydi.

## O'rnatish

1. Virtual environment yarating.
2. Dependency o'rnating:

```bash
pip install -r requirements.txt
```

3. `.env.example` ni `.env` ga ko'chirib to'ldiring.

## Google Sheets ni avtomat tayyorlash

Google tomonda to'liq nol-konfiguratsiya imkoni yo'q: kamida 1 marta service account JSON kalit kerak bo'ladi.
Lekin undan keyin jadval yaratish, tab va ustunlarni tayyorlashni bitta komandaga avtomatlashtirdik.

Mavjud sheet URL bilan:

```bash
python -m telegramautomation.bootstrap \
	--service-account-file C:/keys/service-account.json \
	--sheet-url "https://docs.google.com/spreadsheets/d/xxxx/edit" \
	--update-env
```

Yangi sheet yaratib avtomat sozlash:

```bash
python -m telegramautomation.bootstrap \
	--service-account-file C:/keys/service-account.json \
	--create-sheet \
	--sheet-title "Telegram Automation" \
	--update-env
```

Eslatma:

- Service account email'ini Google Sheet'ga `Editor` qilib ulash shart.
- Runtime `GOOGLE_SHEET_ID` yoki `GOOGLE_SHEET_URL` dan ishlay oladi.

## Sheet struktura

### contacts

Kerakli ustunlar:

- `row_id`
- `username`
- `phone`
- `chat_id`
- `template_id`
- `payload_type` (`text`, `file`, `text_file`)
- `payload_ref`
- `send_after` (ISO datetime, ixtiyoriy)
- `priority` (int)
- `enabled` (`true`/`false`)
- `state` (`pending`, `retry`, `delayed`, `sent`, `failed`)
- `attempts` (int)
- `last_error`
- `sent_at`
- `message_id`

### templates

- `template_id`
- `text`
- `file_ref`
- `parse_mode`
- `active`

### settings

- `key`
- `value`

Qo'llab-quvvatlanadigan keylar:

- `batch_size`
- `interval_hours`
- `min_delay_seconds`
- `max_retries`

## Ishga tushirish

```bash
python -m telegramautomation
```

Agent `POLL_INTERVAL_SECONDS` oralig'ida ishlaydi va har safar navbatdagi jo'natmalarni qayta hisoblaydi.

## Telegramdan boshqarish

Tizim Telegram buyruqlari orqali `settings` sheetni tahrir qila oladi.

Muhim: commandlar SQL'ni emas, Google Sheet `settings` ni yangilaydi.
`runtime/state.db` esa faqat yuborish eventlari va limit oynasi hisoblari uchun ishlatiladi.

`env`:

- `ENABLE_TELEGRAM_CONTROL=true`
- `ADMIN_CHAT_IDS=123456789` (vergul bilan bir nechta id berish mumkin)

Buyruqlar:

- `/settings`
- `/set <key> <value>` (`batch_size`, `interval_hours`, `min_delay_seconds`, `max_retries`)
- `/setbatch <n>`
- `/setinterval <hours>`
- `/setdelay <seconds>`
- `/setretries <n>`
- `/runonce`

`max_retries` ma'nosi: yuborish xato bo'lsa, shu qiymatgacha qayta urinadi. Limitdan oshsa `failed` bo'ladi.

## Qo'shimcha qulayliklar

- `row_id` bo'sh bo'lsa, agent uni avtomatik yaratib `contacts` sheetga yozadi.
- `username` yoki `phone` (yoki `chat_id`) kiritilgan yangi qatorlarda quyidagilar avtomatik default bo'ladi:
	- `row_id=auto_...`
	- `payload_type=text`
	- `priority=100`
	- `enabled=true`
	- `state=pending`
	- `attempts=0`
- Sheet ko'rinishini setka va header style bilan avtomat formatlash mumkin:

```bash
python scripts/format_sheet_grid.py
```

- Doimiy kuzatuv rejimi ham bor: servis har cycle'da yangi rowlarni tekshiradi va borderni avtomat yangilaydi.
- `last_error` ustuni avtomatik qizil rangda formatlanadi.
- `enabled` ustuni: `true` bo'lsa yashil, `false` bo'lsa qizil ko'rinishda bo'ladi.
- `template_id` ustunida optionlar `templates` sheetdagi `template_id` qiymatlaridan dropdown bo'lib chiqadi.
- `ENABLE_CONTACTS_COMPACT=true` bo'lsa username/phone/chat_id bo'sh qolgan ortiqcha qatorlar avtomatik o'chiriladi va jadval zichlanadi.

`env`:

- `ENABLE_AUTO_GRID_FORMAT=true`
- `AUTO_GRID_CHECK_EVERY_CYCLES=1` (har cycle; 2 bo'lsa har ikkinchi cycle)
