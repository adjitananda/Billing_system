# Скрипты биллинговой системы

## daily_billing.py
Скрипт для ежедневного автоматического расчёта биллинга.

### Использование
```bash
# Активировать виртуальное окружение
source venv/bin/activate

# Расчёт за сегодня
python scripts/daily_billing.py

# Расчёт за вчера
python scripts/daily_billing.py --yesterday

# Расчёт за конкретную дату
python scripts/daily_billing.py --date 2025-03-22

# Принудительная перезапись (если записи уже существуют)
python scripts/daily_billing.py --date 2025-03-22 --force

# Режим просмотра (без внесения изменений)
python scripts/daily_billing.py --date 2025-03-22 --dry-run