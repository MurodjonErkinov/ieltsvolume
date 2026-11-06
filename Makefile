COMPOSE = docker compose

.PHONY: help build up down restart logs ps migrate makemigrations superuser shell check

help:
	@echo "make build          Docker image yaratish"
	@echo "make up             Django va PostgreSQL ishga tushirish"
	@echo "make down           Konteynerlarni to'xtatish (baza saqlanadi)"
	@echo "make restart        Konteynerlarni qayta ishga tushirish"
	@echo "make logs           Loglarni kuzatish"
	@echo "make ps             Konteynerlar holati"
	@echo "make migrate        Migratsiyalarni qo'llash"
	@echo "make makemigrations Migratsiya yaratish"
	@echo "make superuser      Admin yaratish"
	@echo "make shell          Django shell"
	@echo "make check          Django sozlamalarini tekshirish"

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

migrate:
	$(COMPOSE) run --rm web python manage.py migrate

makemigrations:
	$(COMPOSE) run --rm web python manage.py makemigrations

superuser:
	$(COMPOSE) run --rm web python manage.py createsuperuser

shell:
	$(COMPOSE) run --rm web python manage.py shell

check:
	$(COMPOSE) run --rm web python manage.py check
