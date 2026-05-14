// grafico.js - Funciones relacionadas con la gráfica

let chart = null;

function crearGrafica(analisisArrayAsc, idxCompra, idxMaxGanancia) {
    const container = document.getElementById('graficaContainer');
    if (!container) return;
    
    container.innerHTML = '';
    
    chart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: 500,
        layout: {
            background: { color: '#ffffff' },
            textColor: '#333',
        },
        grid: {
            vertLines: { color: '#f0f0f0' },
            horzLines: { color: '#f0f0f0' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
        rightPriceScale: {
            borderColor: '#d1d4dc',
        },
        timeScale: {
            borderColor: '#d1d4dc',
            timeVisible: true,
            secondsVisible: false,
        },
    });
    
    // Preparar datos para la línea de precio
    const lineData = [];
    for (let i = 0; i < analisisArrayAsc.length; i++) {
        const a = analisisArrayAsc[i];
        const fecha = new Date(a.fecha);
        const time = Math.floor(fecha.getTime() / 1000);
        lineData.push({ time: time, value: a.precio_cierre });
    }
    
    // Añadir serie de línea AZUL
    const lineSeries = chart.addLineSeries({
        color: '#2c7da0',
        lineWidth: 2,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 4,
        crosshairMarkerBorderColor: '#2c7da0',
        crosshairMarkerBackgroundColor: '#ffffff',
        priceLineVisible: true,
        lastValueVisible: true,
    });
    lineSeries.setData(lineData);
    
    // Preparar marcadores de colores según el caso (SIN TEXTO - solo color)
    const markers = [];
    
    for (let i = 0; i < analisisArrayAsc.length; i++) {
        const a = analisisArrayAsc[i];
        const fecha = new Date(a.fecha);
        const time = Math.floor(fecha.getTime() / 1000);
        
        let markerColor = '';
        if (CASOS_COMPRA_REAL.includes(a.caso_numero)) {
            markerColor = '#1e7e34';  // Verde - COMPRA
        } else if (CASOS_ESPERA.includes(a.caso_numero)) {
            markerColor = '#e68a2e';  // Naranja - ESPERA
        } else if (a.caso_numero === 4) {
            markerColor = '#2c7da0';  // Azul - CONSOLIDACIÓN
        } else {
            markerColor = '#8ba0bc';  // Gris - SIN SEÑAL
        }
        
        markers.push({
            time: time,
            position: 'aboveBar',
            color: markerColor,
            shape: 'circle',
            size: 1,
        });
    }
    
    // Añadir marcador especial para COMPRA
    if (idxCompra !== -1) {
        const compra = analisisArrayAsc[idxCompra];
        const compraTime = Math.floor(new Date(compra.fecha).getTime() / 1000);
        markers.push({
            time: compraTime,
            position: 'aboveBar',
            color: '#1e7e34',
            shape: 'arrowUp',
            text: '🔴 COMPRA',
            size: 2,
        });
    }
    
    // Añadir marcador especial para MÁXIMO BENEFICIO
    if (idxMaxGanancia !== -1 && idxMaxGanancia !== idxCompra) {
        const maxReg = analisisArrayAsc[idxMaxGanancia];
        const maxTime = Math.floor(new Date(maxReg.fecha).getTime() / 1000);
        markers.push({
            time: maxTime,
            position: 'aboveBar',
            color: '#ff9800',
            shape: 'arrowUp',
            text: '🏆 MÁXIMO BENEFICIO',
            size: 2,
        });
    }
    
    lineSeries.setMarkers(markers);
    chart.timeScale().fitContent();
    
    window.addEventListener('resize', () => {
        if (chart) {
            chart.applyOptions({ width: container.clientWidth });
        }
    });
}

function limpiarGrafica() {
    if (chart) {
        chart = null;
    }
}
