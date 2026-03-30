// Калькулятор what-if анализа цен

document.addEventListener('DOMContentLoaded', function() {
    // Элементы формы
    const calcTypeRadios = document.querySelectorAll('input[name="calculation_type"]');
    const clientSelectBlock = document.getElementById('client-select-block');
    const serverIdBlock = document.getElementById('server-id-block');
    const calculateBtn = document.getElementById('calculate-btn');
    const resultsContainer = document.getElementById('results-container');
    
    // Переключение видимости полей
    function toggleFields() {
        const selectedType = document.querySelector('input[name="calculation_type"]:checked').value;
        clientSelectBlock.style.display = selectedType === 'client' ? 'block' : 'none';
        serverIdBlock.style.display = selectedType === 'server' ? 'block' : 'none';
    }
    
    calcTypeRadios.forEach(radio => radio.addEventListener('change', toggleFields));
    toggleFields();
    
    // Форматирование чисел
    function formatNumber(value) {
        return new Intl.NumberFormat('ru-RU', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(value);
    }
    
    // Отрисовка таблицы результатов
    function renderResults(data) {
        if (!data || data.length === 0) {
            resultsContainer.innerHTML = '<div class="alert alert-warning">Нет данных для отображения</div>';
            return;
        }
        
        let html = '';
        for (const client of data) {
            html += `
                <div class="card mb-4">
                    <div class="card-header bg-primary text-white">
                        <h5 class="mb-0">Клиент: ${client.client_name}</h5>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-striped table-bordered">
                                <thead>
                                    <tr>
                                        <th>Сервер</th>
                                        <th>Текущая Ст./День</th>
                                        <th>Текущая Ст./31 День</th>
                                        <th>Расчётная Ст./День</th>
                                        <th>Расчётная Ст./31 День</th>
                                        <th>С наценкой Ст./День</th>
                                        <th>С наценкой Ст./31 День</th>
                                    </tr>
                                </thead>
                                <tbody>
            `;
            
            for (const server of client.servers) {
                html += `
                    <tr>
                        <td>${server.server_name}</td>
                        <td class="text-end">${formatNumber(server.current_daily)} ₽</td>
                        <td class="text-end">${formatNumber(server.current_monthly)} ₽</td>
                        <td class="text-end">${formatNumber(server.calculated_daily)} ₽</td>
                        <td class="text-end">${formatNumber(server.calculated_monthly)} ₽</td>
                        <td class="text-end">${formatNumber(server.markedup_daily)} ₽</td>
                        <td class="text-end">${formatNumber(server.markedup_monthly)} ₽</td>
                    </tr>
                `;
            }
            
            html += `
                                </tbody>
                                <tfoot class="table-secondary fw-bold">
                                    <tr>
                                        <td>ИТОГО по клиенту</td>
                                        <td class="text-end">${formatNumber(client.client_current_daily)} ₽</td>
                                        <td class="text-end">${formatNumber(client.client_current_monthly)} ₽</td>
                                        <td class="text-end">${formatNumber(client.client_calculated_daily)} ₽</td>
                                        <td class="text-end">${formatNumber(client.client_calculated_monthly)} ₽</td>
                                        <td class="text-end">${formatNumber(client.client_markedup_daily)} ₽</td>
                                        <td class="text-end">${formatNumber(client.client_markedup_monthly)} ₽</td>
                                    </tr>
                                </tfoot>
                            </table>
                        </div>
                    </div>
                </div>
            `;
        }
        resultsContainer.innerHTML = html;
    }
    
    // Обработка расчета
    calculateBtn.addEventListener('click', async function() {
        const calculationType = document.querySelector('input[name="calculation_type"]:checked').value;
        const clientId = document.getElementById('client_id')?.value;
        const serverId = document.getElementById('server_id')?.value;
        const markupPercent = parseFloat(document.getElementById('markup_percent').value) || 0;
        
        const customPrices = {
            cpu: parseFloat(document.getElementById('price_cpu').value) || 0,
            ram: parseFloat(document.getElementById('price_ram').value) || 0,
            nvme: parseFloat(document.getElementById('price_nvme').value) || 0,
            hdd: parseFloat(document.getElementById('price_hdd').value) || 0
        };
        
        const payload = {
            calculation_type: calculationType,
            custom_prices: customPrices,
            markup_percent: markupPercent
        };
        
        if (calculationType === 'client' && clientId) {
            payload.client_id = parseInt(clientId);
        }
        if (calculationType === 'server' && serverId) {
            payload.server_id = parseInt(serverId);
        }
        
        resultsContainer.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"></div><br>Расчёт...</div>';
        
        try {
            const response = await fetch('/api/v1/calculator/calculate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Ошибка расчета');
            }
            
            const data = await response.json();
            renderResults(data);
        } catch (error) {
            resultsContainer.innerHTML = `<div class="alert alert-danger">Ошибка: ${error.message}</div>`;
        }
    });
});
