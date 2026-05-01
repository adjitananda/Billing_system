// Коммерческое предложение

let currentQuoteData = null;

// Открытие модального окна
async function openQuoteModal(clientId, clientName) {
    // Показываем форму, скрываем результат
    document.getElementById('quoteFormState').style.display = 'block';
    document.getElementById('quoteResultState').style.display = 'none';
    
    // Загружаем текущие цены
    try {
        const response = await fetch('/current-prices');
        const prices = await response.json();
        
        document.getElementById('price_cpu').value = prices.cpu;
        document.getElementById('price_ram').value = prices.ram;
        document.getElementById('price_nvme').value = prices.nvme;
        document.getElementById('price_hdd').value = prices.hdd;
    } catch (error) {
        console.error('Ошибка загрузки цен:', error);
    }
    
    // Сохраняем clientId для генерации
    document.getElementById('generateQuoteBtn').onclick = () => generateQuote(clientId);
    
    // Показываем модальное окно
    const modal = new bootstrap.Modal(document.getElementById('quoteModal'));
    modal.show();
}

// Генерация КП
async function generateQuote(clientId) {
    const custom_prices = {
        cpu: parseFloat(document.getElementById('price_cpu').value),
        ram: parseFloat(document.getElementById('price_ram').value),
        nvme: parseFloat(document.getElementById('price_nvme').value),
        hdd: parseFloat(document.getElementById('price_hdd').value)
    };
    const markup_percent = parseFloat(document.getElementById('markup').value);
    
    try {
        const response = await fetch(`/clients/${clientId}/generate-quote`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ custom_prices, markup_percent })
        });
        
        if (!response.ok) throw new Error('Ошибка генерации');
        
        currentQuoteData = await response.json();
        displayQuoteResult(currentQuoteData);
        
        // Скрываем форму, показываем результат
        document.getElementById('quoteFormState').style.display = 'none';
        document.getElementById('quoteResultState').style.display = 'block';
        
    } catch (error) {
        alert('Ошибка: ' + error.message);
    }
}

// Отображение результата
function displayQuoteResult(data) {
    // Заголовок
    document.getElementById('quoteDate').innerHTML = `<strong>Клиент:</strong> ${data.client_name}<br><strong>Дата:</strong> ${data.date}<br><strong>Наценка:</strong> ${data.markup_percent}%`;
    
    // Таблица серверов
    const tbody = document.getElementById('quoteTableBody');
    tbody.innerHTML = '';
    
    data.servers.forEach(server => {
        const row = tbody.insertRow();
        row.insertCell(0).textContent = server.server_name;
        row.insertCell(1).textContent = server.cpu;
        row.insertCell(2).textContent = server.ram;
        row.insertCell(3).textContent = server.nvme_disk;
        row.insertCell(4).textContent = server.hdd_disk;
        row.insertCell(5).textContent = `${server.price_per_day.toFixed(2)} ₽`;
        row.insertCell(6).textContent = `${server.price_per_30_days.toFixed(2)} ₽`;
    });
    
    // Итоги
    document.getElementById('total_cpu').textContent = data.totals.cpu;
    document.getElementById('total_ram').textContent = data.totals.ram;
    document.getElementById('total_nvme').textContent = data.totals.nvme;
    document.getElementById('total_hdd').textContent = data.totals.hdd;
    document.getElementById('total_price_day').textContent = `${data.totals.price_per_day.toFixed(2)} ₽`;
    document.getElementById('total_price_month').textContent = `${data.totals.price_per_30_days.toFixed(2)} ₽`;
    
    // Кнопки
    document.getElementById('copyTextBtn').onclick = copyQuoteText;
    document.getElementById('downloadCsvBtn').onclick = downloadQuoteCsv;
}

// Копирование текста
function copyQuoteText() {
    if (!currentQuoteData) return;
    
    let text = `КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ\n`;
    text += `Клиент: ${currentQuoteData.client_name}\n`;
    text += `Дата: ${currentQuoteData.date}\n`;
    text += `Наценка: ${currentQuoteData.markup_percent}%\n\n`;
    text += `Сервер\tCPU\tRAM\tNVMe\tHDD\tСт./день\tСт./30 дней\n`;
    
    currentQuoteData.servers.forEach(s => {
        text += `${s.server_name}\t${s.cpu}\t${s.ram}\t${s.nvme_disk}\t${s.hdd_disk}\t${s.price_per_day.toFixed(2)} ₽\t${s.price_per_30_days.toFixed(2)} ₽\n`;
    });
    
    text += `\nИТОГО:\t${currentQuoteData.totals.cpu}\t${currentQuoteData.totals.ram}\t${currentQuoteData.totals.nvme}\t${currentQuoteData.totals.hdd}\t${currentQuoteData.totals.price_per_day.toFixed(2)} ₽\t${currentQuoteData.totals.price_per_30_days.toFixed(2)} ₽\n`;
    
    navigator.clipboard.writeText(text);
    alert('Скопировано в буфер обмена');
}

// Скачивание CSV
function downloadQuoteCsv() {
    if (!currentQuoteData) return;
    
    let csv = "Сервер,CPU,RAM,NVMe,HDD,Ст./день (₽),Ст./30 дней (₽)\n";
    
    currentQuoteData.servers.forEach(s => {
        csv += `${s.server_name},${s.cpu},${s.ram},${s.nvme_disk},${s.hdd_disk},${s.price_per_day.toFixed(2)},${s.price_per_30_days.toFixed(2)}\n`;
    });
    
    csv += `ИТОГО,,${currentQuoteData.totals.cpu},${currentQuoteData.totals.ram},${currentQuoteData.totals.nvme},${currentQuoteData.totals.hdd},${currentQuoteData.totals.price_per_day.toFixed(2)},${currentQuoteData.totals.price_per_30_days.toFixed(2)}\n`;
    
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.href = url;
    link.setAttribute('download', `quote_client_${currentQuoteData.client_id}_${currentQuoteData.date}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}
