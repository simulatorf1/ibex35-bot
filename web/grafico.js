// grafico.js
const CASOS_COMPRA_REAL = [1, 6];
const CASOS_ESPERA = [2, 3, 5, 7];

let chart = null;

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
        const time = Math.floor(new Date(a.fecha).getTime() / 1000);
        let markerColor = '';
        if (CASOS_COMPRA_REAL.includes(a.caso_numero)) markerColor = '#1e7e34';
        else if (CASOS_ESPERA.includes(a.caso_numero)) markerColor = '#e68a2e';
        else if (a.caso_numero === 4) markerColor = '#2c7da0';
        else markerColor = '#8ba0bc';
        
        markers.push({ time: time, position: 'aboveBar', color: markerColor, shape: 'circle', size: 1 });
    }
    
    if (idxCompra !== -1) {
        const compraTime = Math.floor(new Date(analisisArrayAsc[idxCompra].fecha).getTime() / 1000);
        markers.push({ time: compraTime, position: 'aboveBar', color: '#1e7e34', shape: 'arrowUp', text: '🔴 COMPRA', size: 2 });
    }
    
    if (idxMaxGanancia !== -1 && idxMaxGanancia !== idxCompra) {
        const maxTime = Math.floor(new Date(analisisArrayAsc[idxMaxGanancia].fecha).getTime() / 1000);
        markers.push({ time: maxTime, position: 'aboveBar', color: '#ff9800', shape: 'arrowUp', text: '🏆 MÁXIMO BENEFICIO', size: 2 });
    }
    
    lineSeries.setMarkers(markers);
    chart.timeScale().fitContent();
    
    window.addEventListener('resize', () => { if (chart) chart.applyOptions({ width: container.clientWidth }); });
}

function limpiarGrafica() {
    if (chart) { chart = null; }
}
