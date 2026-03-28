# Импорт исторических данных

## 1. Подготовка файлов

### Файл событий (events.csv)

Создайте CSV-файл со следующими колонками:
- `date` — дата в формате YYYY-MM-DD
- `event` — тип события: `activate`, `deactivate`, `change`
- `server_name` — название сервера (уникально в рамках клиента)
- `client_name` — название клиента
- `physical_server_name` — название физического сервера (хоста)
- `cpu_cores` — количество ядер CPU (для activate/change)
- `ram_gb` — RAM в ГБ (для activate/change)
- `nvme1_gb` — размер NVMe диска 1 в ГБ (опционально)
- `nvme2_gb` — размер NVMe диска 2 в ГБ (опционально)
- `nvme3_gb` — размер NVMe диска 3 в ГБ (опционально)
- `nvme4_gb` — размер NVMe диска 4 в ГБ (опционально)
- `nvme5_gb` — размер NVMe диска 5 в ГБ (опционально)
- `hdd_gb` — размер HDD в ГБ (опционально)

**Важно:**
- Для события `deactivate` поля ресурсов могут быть пустыми
- Для `activate` и `change` поля `cpu_cores` и `ram_gb` обязательны
- Дисковые поля: если не указаны — считаются равными 0

#### Пример файла событий (events.csv):
```csv
date,event,server_name,client_name,physical_server_name,cpu_cores,ram_gb,nvme1_gb,nvme2_gb,nvme3_gb,nvme4_gb,nvme5_gb,hdd_gb
2025-10-20,activate,web01,ООО Ромашка,Host-01,4,8,100,0,0,0,0,50
2025-10-21,activate,db01,ООО Ромашка,Host-01,8,16,200,100,0,0,0,100
2025-10-25,activate,app01,ИП Иванов,Host-02,2,4,0,0,0,0,0,50
2025-11-03,deactivate,web01,ООО Ромашка,Host-01,,,,,,,,,
2025-11-07,change,db01,ООО Ромашка,Host-01,12,32,200,200,100,0,0,200
2025-11-15,activate,backup01,ООО Ромашка,Host-02,4,8,500,0,0,0,0,1000
2025-12-01,change,app01,ИП Иванов,Host-02,4,8,100,0,0,0,0,0