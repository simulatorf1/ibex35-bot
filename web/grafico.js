// grafico.js
const CASOS_COMPRA_REAL = [1, 6];
const CASOS_ESPERA = [2, 3, 5, 7];

// Colores para cada caso (los que quieres mostrar)
const COLOR_CASO = {
    1: '#1e7e34',  // Verde oscuro - Compra Inmediata
    2: '#ffc107',  // Amarillo - Compra Anticipada
    3: '#000000',  // NEGRO - Rebote corto
    5: '#dc3545',  // Rojo - Agotamiento
    6: '#28a745',  // Verde claro - Compra Rápida
    7: '#17a2b8'   // Cyan - Pre-Compra
};

let chart = null;

function getColorForCaso(casoNumero) {
    // Caso 4 y sin señal: NO tienen color
    if (casoNumero === 4) return null;
    if (casoNumero === null || casoNumero === undefined) return null;
    if (COLOR_CASO[casoNumero]) return COLOR_CASO[casoNumero];
    return null;
}

function crearGrafica(analisisArrayAsc, idxCompra, idxMaxGanancia) {
    const container = document.getElementById('graficaContainer');
    if (!container) return;
    
    container.innerHTML = '';
    
    chart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: 500,
        layout: { background: { color: '#ffffff' }, textColor: '#333' },
        grid: { vertLines: { color: '#f0f0f0' }, horzLines: { color: '#f0f0f0' } },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        rightPriceScale: { borderColor: '#d1d4dc' },
        timeScale: { borderColor: '#d1d4dc', timeVisible: true, secondsVisible: false }
    });
    
    const lineData = [];
    for (let i = 0; i < analisisArrayAsc.length; i++) {
        const a = analisisArrayAsc[i];
        const time = Math.floor(new Date(a.fecha).getTime() / 1000);
        lineData.push({ time: time, value: a.precio_cierre });
    }
    
    const lineSeries = chart.addLineSeries({
        color: '#2c7da0',
        lineWidth: 2,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 4,
        priceLineVisible: true,
        lastValueVisible: true
    });
    lineSeries.setData(lineData);
    
    const markers = [];
    for (let i = 0; i < analisisArrayAsc.length; i++) {
        const a = analisisArrayAsc[i];
        const markerColor = getColorForCaso(a.caso_numero);
        if (markerColor !== null) {
            const time = Math.floor(new Date(a.fecha).getTime() / 1000);
            markers.push({ 
                time: time, 
                position: 'aboveBar', 
                color: markerColor, 
                shape: 'circle', 
                size: 1
            });
        }
    }
    
    if (idxCompra !== -1) {
        const compraTime = Math.floor(new Date(analisisArrayAsc[idxCompra].fecha).getTime() / 1000);
        markers.push({ 
            time: compraTime, 
            position: 'aboveBar', 
            color: '#1e7e34', 
            shape: 'arrowUp', 
            text: '🔴 COMPRA', 
            size: 2 
        });
    }
    
    if (idxMaxGanancia !== -1 && idxMaxGanancia !== idxCompra) {
        const maxTime = Math.floor(new Date(analisisArrayAsc[idxMaxGanancia].fecha).getTime() / 1000);
        markers.push({ 
            time: maxTime, 
            position: 'aboveBar', 
            color: '#ff9800', 
            shape: 'arrowUp', 
            text: '🏆 MÁXIMO BENEFICIO', 
            size: 2 
        });
    }
    
    lineSeries.setMarkers(markers);
    chart.timeScale().fitContent();
    
    // Añadir leyenda FUERA del gráfico (después del contenedor)
    crearLeyenda(container);
    
    window.addEventListener('resize', () => { 
        if (chart) chart.applyOptions({ width: container.clientWidth }); 
    });
}

function crearLeyenda(container) {
    // Buscar si ya existe una leyenda para no duplicar
    let legendDiv = document.getElementById('graficoLeyenda');
    if (legendDiv) {
        legendDiv.remove();
    }
    
    legendDiv = document.createElement('div');
    legendDiv.id = 'graficoLeyenda';
    legendDiv.style.cssText = `
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        padding: 10px 16px;
        background: #f8f9fa;
        border-radius: 12px;
        margin-top: 12px;
        font-size: 0.7rem;
        border: 1px solid #e9ecef;
        justify-content: center;
    `;
    
    const items = [
        { color: COLOR_CASO[1], text: 'Caso 1 - Compra Inmediata' },
        { color: COLOR_CASO[2], text: 'Caso 2 - Compra Anticipada' },
        { color: COLOR_CASO[3], text: 'Caso 3 - Rebote corto' },
        { color: COLOR_CASO[5], text: 'Caso 5 - Agotamiento' },
        { color: COLOR_CASO[6], text: 'Caso 6 - Compra Rápida' },
        { color: COLOR_CASO[7], text: 'Caso 7 - Pre-Compra' },
        { color: '#ff9800', text: '🏆 Máximo beneficio' }
    ];
    
    for (const item of items) {
        const itemDiv = document.createElement('div');
        itemDiv.style.cssText = 'display: flex; align-items: center; gap: 6px;';
        itemDiv.innerHTML = `
            <div style="width: 14px; height: 14px; background: ${item.color}; border-radius: 50%;"></div>
            <span style="color: #495057;">${item.text}</span>
        `;
        legendDiv.appendChild(itemDiv);
    }
    
    // Poner la leyenda DESPUÉS del contenedor del gráfico (por fuera)
    container.parentNode.insertBefore(legendDiv, container.nextSibling);
}

function limpiarGrafica() {
    // Limpiar también la leyenda
    const legend = document.getElementById('graficoLeyenda');
    if (legend) legend.remove();
    if (chart) { chart = null; }
}
