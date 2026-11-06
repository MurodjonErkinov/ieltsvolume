# IELTS Volume

Python 3.12+ (jumladan 3.14), Django 5.2 va PostgreSQL 14+ asosidagi boshlang'ich loyiha.

## Talablar va database schema

[Kelishilgan talablar](docs/requirements.md) · [Schema tavsifi](docs/database-schema.md) · [DBML diagramma](docs/database.dbml)

Django modellar va boshlang‘ich migratsiyalar tayyor: `accounts`, `exams`, `billing`,
`attempts`, `notifications`. Chek tasdig‘i, bir martalik access/urinish va AI/mentor
tekshiruvlarini ajratish uchun asosiy transaction servislar mavjud.

Hozircha custom dashboardlar, Telegram bot, imtihon oynasi, avtomatik baholash va AI
integratsiyasi yozilmagan. Notification yozuvlari navbatga qo‘shiladi, tashqi xabarlar
hali yuborilmaydi. `/admin/` standart Django adminidir; yangi modellar biznes
qoidalarini chetlab o‘tmaslik uchun unda bevosita tahrirlashga ro‘yxatdan o‘tkazilmagan.

```bash
docker compose exec -T web python manage.py check
docker compose exec -T web python manage.py test --noinput
docker compose exec -T web python manage.py makemigrations --check --dry-run
docker compose exec -T web python manage.py shell < scripts/export_schema.py
```

## O'rnatish

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -c 'import secrets; print(secrets.token_urlsafe(50))'
```

Oxirgi buyruq chiqargan kalitni `.env` ichidagi `DJANGO_SECRET_KEY` qiymatiga yozing.
PostgreSQL ulanish ma'lumotlarini ham `.env` orqali sozlang.

## PostgreSQL

PostgreSQL serverini ishga tushiring va administrator sifatida `psql postgres` konsoliga kirib, quyidagilarni bajaring:

```sql
CREATE USER ieltsvolume WITH PASSWORD 'change-me';
CREATE DATABASE ieltsvolume OWNER ieltsvolume;
```

Parolni o'zingiz tanlang va `.env` dagi `POSTGRES_PASSWORD` bilan bir xil qiling.

## Docker orqali ishga tushirish

Docker Compose v2 va Make kerak. Yuqoridagi kabi `.env` faylini tayyorlang
va maxfiy kalit hamda baza parolini belgilang. Docker bazani o'zi yaratadi;
yuqoridagi SQL buyruqlarini bajarish shart emas.

```bash
make up
make migrate
make superuser
```

Admin panel: http://127.0.0.1:8019/admin/

Docker portlari: Django `127.0.0.1:8019`, PostgreSQL `127.0.0.1:5439`.
Ularni `.env` ichidagi `WEB_PORT` va `POSTGRES_PORT` orqali o'zgartirish mumkin.

`make help` barcha buyruqlarni ko'rsatadi. `make logs` loglarni ochadi,
`make down` konteynerlarni to'xtatadi va bazadagi ma'lumotlarni saqlaydi.
PostgreSQL ma'lumotlari `postgres_data` Docker volume ichida saqlanadi.
Compose Django uchun `POSTGRES_HOST=db` va `POSTGRES_PORT=5432` qiymatlarini
o'rnatadi. Kod papkasi konteynerga ulangan, o'zgarishlar avtomatik yuklanadi.
Bu Docker konfiguratsiyasi lokal ishlab chiqish uchun mo'ljallangan.

## Ishga tushirish

```bash
python manage.py check
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

- Admin panel: http://127.0.0.1:8000/admin/

`config/` sozlamalar va asosiy URL konfiguratsiyasini saqlaydi.

Serverga joylashdan oldin `DJANGO_DEBUG=False`, tegishli `DJANGO_ALLOWED_HOSTS` va HTTPS xavfsizlik sozlamalarini belgilang. `runserver` lokal ishlab chiqish uchun mo'ljallangan.
