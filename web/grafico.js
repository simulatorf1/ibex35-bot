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
let currentData = null;
let currentDataCompra = null;
let currentDataMax = null;
let currentSoportes = null;
let currentResistencias = null;
let currentView = 'all';

function getColorForCaso(casoNumero) {
    if (casoNumero === 4) return null;
    if (casoNumero === null || casoNumero === undefined) return null;
    if (COLOR_CASO[casoNumero]) return COLOR_CASO[casoNumero];
    return null;
}

function agruparPorDia(analisisArrayAsc) {
    const dailyMap = new Map();
    for (const registro of analisisArrayAsc) {
        const fechaKey = new Date(registro.fecha).toISOString().split('T')[0];
        if (!dailyMap.has(fechaKey) || new Date(registro.fecha) > new Date(dailyMap.get(fechaKey).fecha)) {
            dailyMap.set(fechaKey, registro);
        }
    }
    const dailyArray = Array.from(dailyMap.values());
    dailyArray.sort((a, b) => new Date(a.fecha) - new Date(b.fecha));
    return dailyArray;
}

function extraerNivelesNumericos(texto) {
    if (!texto || texto === 'No hay datos') return [];
    const lineas = texto.split('\n');
    const numeros = [];
    for (let linea of lineas) {
        linea = linea.trim();
        if (!linea) continue;
        const rangoMatch = linea.match(/([\d\.]+)\s*-\s*([\d\.]+)/);
        if (rangoMatch) {
            numeros.push(parseFloat(rangoMatch[1].replace(/\./g, '')));
            numeros.push(parseFloat(rangoMatch[2].replace(/\./g, '')));
        } else {
            const numMatch = linea.match(/([\d\.]+)/);
            if (numMatch) numeros.push(parseFloat(numMatch[1].replace(/\./g, '')));
        }
    }
    const unicos = [...new Set(numeros)];
    unicos.sort((a, b) => a - b);
    return unicos.slice(0, 3);
}

function crearGrafica(analisisArrayAsc, idxCompra, idxMaxGanancia, soportesTexto, resistenciasTexto) {
    const container = document.getElementById('graficaContainer');
    if (!container) return;
    
    // Guardar datos originales y los índices para cambiar vista después
    currentData = analisisArrayAsc;
    currentDataCompra = idxCompra;
    currentDataMax = idxMaxGanancia;
    currentSoportes = soportesTexto;
    currentResistencias = resistenciasTexto;
    
    let dataToShow = currentView === 'daily' ? agruparPorDia(analisisArrayAsc) : analisisArrayAsc;
    
    let newIdxCompra = -1;
    let newIdxMaxGanancia = -1;
    
    if (idxCompra !== -1) {
        const compraReg = analisisArrayAsc[idxCompra];
        if (currentView === 'daily') {
            const dailyData = dataToShow;
            const compraFecha = new Date(compraReg.fecha).toISOString().split('T')[0];
            newIdxCompra = dailyData.findIndex(r => new Date(r.fecha).toISOString().split('T')[0] === compraFecha);
        } else {
            newIdxCompra = idxCompra;
        }
    }
    
    if (idxMaxGanancia !== -1 && idxMaxGanancia !== idxCompra) {
        const maxReg = analisisArrayAsc[idxMaxGanancia];
        if (currentView === 'daily') {
            const dailyData = dataToShow;
            const maxFecha = new Date(maxReg.fecha).toISOString().split('T')[0];
            newIdxMaxGanancia = dailyData.findIndex(r => new Date(r.fecha).toISOString().split('T')[0] === maxFecha);
        } else {
            newIdxMaxGanancia = idxMaxGanancia;
        }
    }
    
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
    for (let i = 0; i < dataToShow.length; i++) {
        const a = dataToShow[i];
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
    
    // Dibujar líneas de SOPORTE (verde punteado)
    const soportes = extraerNivelesNumericos(soportesTexto);
    for (const nivel of soportes) {
        const nivelNumerico = nivel / 1000;
        const lineSeriesSoporte = chart.addLineSeries({
            color: '#1e7e34',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dotted,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false
        });
        const lineDataSoporte = [
            { time: lineData[0].time, value: nivelNumerico },
            { time: lineData[lineData.length - 1].time, value: nivelNumerico }
        ];
        lineSeriesSoporte.setData(lineDataSoporte);
    }
    
    // Dibujar líneas de RESISTENCIA (rojo punteado)
    const resistencias = extraerNivelesNumericos(resistenciasTexto);
    for (const nivel of resistencias) {
        const nivelNumerico = nivel / 1000;
        const lineSeriesResistencia = chart.addLineSeries({
            color: '#b91c1c',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dotted,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false
        });
        const lineDataResistencia = [
            { time: lineData[0].time, value: nivelNumerico },
            { time: lineData[lineData.length - 1].time, value: nivelNumerico }
        ];
        lineSeriesResistencia.setData(lineDataResistencia);
    }
    
    const markers = [];
    for (let i = 0; i < dataToShow.length; i++) {
        const a = dataToShow[i];
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
    
    if (newIdxCompra !== -1) {
        const compraTime = Math.floor(new Date(dataToShow[newIdxCompra].fecha).getTime() / 1000);
        markers.push({ 
            time: compraTime, 
            position: 'aboveBar', 
            color: '#1e7e34', 
            shape: 'arrowUp', 
            text: '🔴 COMPRA', 
            size: 2 
        });
    }
    
    if (newIdxMaxGanancia !== -1 && newIdxMaxGanancia !== newIdxCompra) {
        const maxTime = Math.floor(new Date(dataToShow[newIdxMaxGanancia].fecha).getTime() / 1000);
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
    
    // Crear botones si no existen
    crearBotones(container);
    
    // Añadir leyenda
    crearLeyenda(container);
    
    window.addEventListener('resize', () => { 
        if (chart) chart.applyOptions({ width: container.clientWidth }); 
    });
}

function crearBotones(container) {
    let botonesDiv = document.getElementById('graficoBotones');
    if (botonesDiv) {
        const btnTodos = document.getElementById('btnVistaTodos');
        const btnDiario = document.getElementById('btnVistaDiario');
        if (btnTodos && btnDiario) {
            if (currentView === 'all') {
                btnTodos.style.background = '#2c7da0';
                btnTodos.style.color = 'white';
                btnDiario.style.background = 'white';
                btnDiario.style.color = '#2c7da0';
            } else {
                btnTodos.style.background = 'white';
                btnTodos.style.color = '#2c7da0';
                btnDiario.style.background = '#2c7da0';
                btnDiario.style.color = 'white';
            }
        }
        return;
    }
    
    botonesDiv = document.createElement('div');
    botonesDiv.id = 'graficoBotones';
    botonesDiv.style.cssText = `
        display: flex;
        gap: 12px;
        margin-bottom: 16px;
        justify-content: flex-end;
    `;
    
    const btnTodos = document.createElement('button');
    btnTodos.id = 'btnVistaTodos';
    btnTodos.textContent = '📊 Todos los registros';
    btnTodos.style.cssText = `
        padding: 6px 14px;
        border-radius: 20px;
        border: 1px solid #2c7da0;
        background: ${currentView === 'all' ? '#2c7da0' : 'white'};
        color: ${currentView === 'all' ? 'white' : '#2c7da0'};
        cursor: pointer;
        font-size: 0.75rem;
        font-weight: 500;
        transition: all 0.2s;
    `;
    
    const btnDiario = document.createElement('button');
    btnDiario.id = 'btnVistaDiario';
    btnDiario.textContent = '📅 Solo cierres diarios';
    btnDiario.style.cssText = `
        padding: 6px 14px;
        border-radius: 20px;
        border: 1px solid #2c7da0;
        background: ${currentView === 'daily' ? '#2c7da0' : 'white'};
        color: ${currentView === 'daily' ? 'white' : '#2c7da0'};
        cursor: pointer;
        font-size: 0.75rem;
        font-weight: 500;
        transition: all 0.2s;
    `;
    
    btnTodos.onclick = () => {
        if (currentView !== 'all') {
            currentView = 'all';
            if (currentData) {
                crearGrafica(currentData, currentDataCompra, currentDataMax, currentSoportes, currentResistencias);
            }
        }
    };
    
    btnDiario.onclick = () => {
        if (currentView !== 'daily') {
            currentView = 'daily';
            if (currentData) {
                crearGrafica(currentData, currentDataCompra, currentDataMax, currentSoportes, currentResistencias);
            }
        }
    };
    
    botonesDiv.appendChild(btnTodos);
    botonesDiv.appendChild(btnDiario);
    
    container.parentNode.insertBefore(botonesDiv, container);
}

function crearLeyenda(container) {
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
        { color: COLOR_CASO[1], text: 'Compra Inmediata' },
        { color: COLOR_CASO[2], text: 'Compra Anticipada' },
        { color: COLOR_CASO[3], text: 'Rebote corto' },
        { color: COLOR_CASO[5], text: 'Agotamiento' },
        { color: COLOR_CASO[6], text: 'Compra Rápida' },
        { color: COLOR_CASO[7], text: 'Pre-Compra' },
        { color: '#1e7e34', text: '📉 Soporte (línea verde)' },
        { color: '#b91c1c', text: '📈 Resistencia (línea roja)' },
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
    
    container.parentNode.insertBefore(legendDiv, container.nextSibling);
}

function limpiarGrafica() {
    const legend = document.getElementById('graficoLeyenda');
    if (legend) legend.remove();
    const botones = document.getElementById('graficoBotones');
    if (botones) botones.remove();
    if (chart) { chart = null; }
}
