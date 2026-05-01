// Коммерческое предложение

let currentQuoteData = null;
let currentCompetitorsData = null;

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
    
    const markup_percent = {
        cpu: parseFloat(document.getElementById('markup_cpu').value),
        ram: parseFloat(document.getElementById('markup_ram').value),
        nvme: parseFloat(document.getElementById('markup_nvme').value),
        hdd: parseFloat(document.getElementById('markup_hdd').value)
    };
    
    try {
        // Запрос на наши цены
        const response = await fetch(`/clients/${clientId}/generate-quote`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ custom_prices, markup_percent })
        });
        
        if (!response.ok) throw new Error('Ошибка генерации');
        
        currentQuoteData = await response.json();
        displayOurQuote(currentQuoteData);
        
        // Загружаем конкурентов
        await loadCompetitors(clientId);
        
        // Скрываем форму, показываем результат
        document.getElementById('quoteFormState').style.display = 'none';
        document.getElementById('quoteResultState').style.display = 'block';
        
    } catch (error) {
        alert('Ошибка: ' + error.message);
    }
}

// Отображение нашей таблицы
function displayOurQuote(data) {
    const markup = data.markup_percent;
    const markupText = `Клиент: ${data.client_name}<br>Дата: ${data.date}<br>Наценки: CPU +${markup.cpu}%, RAM +${markup.ram}%, NVMe +${markup.nvme}%, HDD +${markup.hdd}%`;
    document.getElementById('quoteInfo').innerHTML = markupText;
    
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
    document.getElementById('copyTextBtn').onclick = () => copyQuoteText();
    document.getElementById('downloadCsvBtn').onclick = () => downloadQuoteCsv();
}

// Загрузка конкурентов
async function loadCompetitors(clientId) {
    try {
        const response = await fetch(`/clients/${clientId}/competitor-quotes`);
        if (!response.ok) return;
        
        currentCompetitorsData = await response.json();
        
        if (currentCompetitorsData.length === 0) return;
        
        // Получаем контейнеры для табов и контента
        const tabsContainer = document.getElementById('competitorTabs');
        const contentContainer = document.getElementById('competitorTabContent');
        
        // Добавляем табы для конкурентов
        for (const comp of currentCompetitorsData) {
            // Добавляем кнопку таба
            const tabLi = document.createElement('li');
            tabLi.className = 'nav-item';
            tabLi.role = 'presentation';
            tabLi.innerHTML = `
                <button class="nav-link" data-bs-toggle="tab" data-bs-target="#competitor${comp.competitor_id}" type="button" role="tab">
                    🏢 ${comp.competitor_name}
                </button>
            `;
            tabsContainer.appendChild(tabLi);
            
            // Добавляем контент таба
            const tabPane = document.createElement('div');
            tabPane.className = 'tab-pane fade';
            tabPane.id = `competitor${comp.competitor_id}`;
            tabPane.role = 'tabpanel';
            tabPane.innerHTML = `<div class="competitor-quote" data-competitor-id="${comp.competitor_id}"></div>`;
            contentContainer.appendChild(tabPane);
            
            // Рендерим таблицу конкурента
            renderCompetitorTable(comp);
        }
    } catch (error) {
        console.error('Ошибка загрузки конкурентов:', error);
    }
}

// Отображение таблицы конкурента
function renderCompetitorTable(competitor) {
    const container = document.querySelector(`#competitor${competitor.competitor_id} .competitor-quote`);
    if (!container) return;
    
    let html = `
        <div class="table-responsive">
            <table class="table table-sm table-bordered">
                <thead>
                    <tr>
                        <th>Сервер</th><th>CPU</th><th>RAM</th><th>NVMe</th><th>HDD</th>
                        <th>Ст./день</th><th>Ст./30 дней</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    for (const server of competitor.servers) {
        html += `
            <tr>
                <td>${server.server_name}</td>
                <td>${server.cpu}</td>
                <td>${server.ram}</td>
                <td>${server.nvme_disk}</td>
                <td>${server.hdd_disk}</td>
                <td class="text-end">${server.price_per_day.toFixed(2)} ₽</td>
                <td class="text-end">${server.price_per_30_days.toFixed(2)} ₽</td>
            </tr>
        `;
    }
    
    html += `
                </tbody>
                <tfoot class="table-active fw-bold">
                    <tr>
                        <td>ИТОГО:</td>
                        <td>${competitor.totals.cpu}</td>
                        <td>${competitor.totals.ram}</td>
                        <td>${competitor.totals.nvme}</td>
                        <td>${competitor.totals.hdd}</td>
                        <td class="text-end">${competitor.totals.price_per_day.toFixed(2)} ₽</td>
                        <td class="text-end">${competitor.totals.price_per_30_days.toFixed(2)} ₽</td>
                    </tr>
                </tfoot>
            </table>
        </div>
    `;
    
    container.innerHTML = html;
}

// Получение активного таба
function getActiveTabData() {
    const activeTab = document.querySelector('#competitorTabs .nav-link.active');
    if (!activeTab) return { type: 'our', data: currentQuoteData };
    
    const targetId = activeTab.getAttribute('data-bs-target');
    if (targetId === '#ourQuote') {
        return { type: 'our', data: currentQuoteData };
    }
    
    // Ищем конкурента
    const competitorId = targetId.replace('#competitor', '');
    const competitor = currentCompetitorsData?.find(c => c.competitor_id == competitorId);
    return { type: 'competitor', data: competitor };
}

// Копирование текста (активного таба)
function copyQuoteText() {
    const active = getActiveTabData();
    
    if (!active.data) {
        alert('Нет данных для копирования');
        return;
    }
    
    let text = '';
    
    if (active.type === 'our') {
        const markup = active.data.markup_percent;
        text = `КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ (НАШИ ЦЕНЫ)\n`;
        text += `Клиент: ${active.data.client_name}\n`;
        text += `Дата: ${active.data.date}\n`;
        text += `Наценки: CPU +${markup.cpu}%, RAM +${markup.ram}%, NVMe +${markup.nvme}%, HDD +${markup.hdd}%\n\n`;
    } else {
        text = `КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ (${active.data.competitor_name})\n`;
        if (active.data.website) text += `Сайт: ${active.data.website}\n`;
        text += `\n`;
    }
    
    text += `Сервер\tCPU\tRAM\tNVMe\tHDD\tСт./день\tСт./30 дней\n`;
    
    active.data.servers.forEach(s => {
        text += `${s.server_name}\t${s.cpu}\t${s.ram}\t${s.nvme_disk}\t${s.hdd_disk}\t${s.price_per_day.toFixed(2)} ₽\t${s.price_per_30_days.toFixed(2)} ₽\n`;
    });
    
    text += `\nИТОГО:\t${active.data.totals.cpu}\t${active.data.totals.ram}\t${active.data.totals.nvme}\t${active.data.totals.hdd}\t${active.data.totals.price_per_day.toFixed(2)} ₽\t${active.data.totals.price_per_30_days.toFixed(2)} ₽\n`;
    
    navigator.clipboard.writeText(text);
    alert('Скопировано в буфер обмена');
}

// Скачивание CSV (активного таба)
function downloadQuoteCsv() {
    const active = getActiveTabData();
    
    if (!active.data) {
        alert('Нет данных для скачивания');
        return;
    }
    
    let csv = '';
    
    if (active.type === 'our') {
        const markup = active.data.markup_percent;
        csv = `# Коммерческое предложение (НАШИ ЦЕНЫ)\n`;
        csv += `# Клиент: ${active.data.client_name}\n`;
        csv += `# Дата: ${active.data.date}\n`;
        csv += `# Наценки: CPU ${markup.cpu}%, RAM ${markup.ram}%, NVMe ${markup.nvme}%, HDD ${markup.hdd}%\n`;
    } else {
        csv = `# Коммерческое предложение (${active.data.competitor_name})\n`;
        if (active.data.website) csv += `# Сайт: ${active.data.website}\n`;
    }
    
    csv += "Сервер,CPU,RAM,NVMe,HDD,Ст./день (₽),Ст./30 дней (₽)\n";
    
    active.data.servers.forEach(s => {
        csv += `${s.server_name},${s.cpu},${s.ram},${s.nvme_disk},${s.hdd_disk},${s.price_per_day.toFixed(2)},${s.price_per_30_days.toFixed(2)}\n`;
    });
    
    csv += `ИТОГО,,${active.data.totals.cpu},${active.data.totals.ram},${active.data.totals.nvme},${active.data.totals.hdd},${active.data.totals.price_per_day.toFixed(2)},${active.data.totals.price_per_30_days.toFixed(2)}\n`;
    
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.href = url;
    const filename = active.type === 'our' 
        ? `quote_our_${active.data.client_id}_${active.data.date}.csv`
        : `quote_${active.data.competitor_name}_${active.data.client_id}_${active.data.date}.csv`;
    link.setAttribute('download', filename.replace(/[^a-zA-Z0-9_\-\.]/g, '_'));
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}
