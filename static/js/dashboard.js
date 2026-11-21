(function () {
    // Gráfico de barras das reservas por mês
    var dados = document.getElementById('dados-por-mes');
    var tela = document.getElementById('grafico-por-mes');
    if (!dados || !tela || typeof Chart === 'undefined') {
        return;
    }
    var serie = JSON.parse(dados.textContent);
    new Chart(tela, {
        type: 'bar',
        data: {
            labels: serie.map(function (item) { return item.mes; }),
            datasets: [{
                label: 'Reservas',
                data: serie.map(function (item) { return item.total; }),
                backgroundColor: '#1f66e0',
                hoverBackgroundColor: '#0b1d47',
                borderRadius: 8,
                maxBarThickness: 48
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#e6ecf7' } },
                x: { grid: { display: false } }
            }
        }
    });
})();
