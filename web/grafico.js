// grafico.js
const CASOS_COMPRA_REAL = [1, 6];
const CASOS_ESPERA = [2, 3, 5, 7];

// Colores para cada caso
const COLOR_CASO = {
    1: '#1e7e34',  // Verde oscuro - Compra Inmediata
    2: '#ffc107',  // Amarillo - Compra Anticipada
    3: '#fd7e14',  // Naranja - Rebote corto
    4: '#2c7da0',  // Azul - Compra Consolidada
    5: '#dc3545',  // Rojo - Agotamiento
    6: '#28a745',  // Verde claro - Compra Rápida
    7: '#17a2b8',  // Cyan - Pre-Compra
    'sin_senal': '#8ba0bc'  // Gris - Sin señal
};

// Texto descriptivo para cada caso
const TEXTO_CASO = {
    1: '🔴 COMPRA INMEDIATA',
    2: '🟡 COMPRA ANTICIPADA',
    3: '🟠 REBOTE CORTO',
    4: '🔵 COMPRA CONSOLIDADA',
    5: '🔴 AGOTAMIENTO',
    6: '🟢 COMPRA RÁPIDA',
    7: '🔷 PRE-COMPRA',
    'sin_senal': '⚪ SIN SEÑAL'
};

let chart = null;
let currentData = null;
let currentView = 'all'; // 'all' o 'daily'

function getColorForCaso(casoNumero) {
    if (casoNumero === null || casoNumero === undefined) return COLOR_CASO.sin_senal;
    if (COLOR_CASO[casoNumero]) return COLOR_CASO[casoNumero];
    return COLOR_CASO.sin_senal;
}

function getTextForCaso(casoNumero) {
    if (casoNumero === null || casoNumero === undefined) return TEXTO_CASO.sin_senal;
    if (TEXTO_CASO[casoNumero]) return TEXTO_CASO[casoNumero];
    return TEXTO_CASO.sin_senal;
}

// Agrupar por día (último precio del día)
function agruparPorDia(analisisArrayAsc) {
    const dailyMap = new Map();
    
    for (const registro of analisisArrayAsc) {
        const fechaKey = new Date(registro.fecha).toISOString().split('T')[0];
        // Guardamos el último registro del día (por índice o por hora)
        if (!dailyMap.has(fechaKey) || new Date(registro.fecha) > new Date(dailyMap.get(fechaKey).fecha)) {
            dailyMap.set(fechaKey, registro);
        }
    }
    
    // Convertir a array ordenado por fecha
    const dailyArray = Array.from(dailyMap.values());
    dailyArray.sort((a, b) => new Date(a.fecha) - new Date(b.fecha));
    
    return dailyArray;
}

function crearGrafica(analisisArrayAsc, idxCompra, idxMaxGanancia) {
    const container = document.getElementById('graficaContainer');
    if (!container) return;
    
    // Guardar datos originales
    currentData = analisisArrayAsc;
    
    // Determinar qué datos mostrar según la vista actual
    let dataToShow = currentView === 'daily' ? agruparPorDia(analisisArrayAsc) : analisisArrayAsc;
    
    // Recalcular índices para la vista actual
    let newIdxCompra = -1;
    let newIdxMaxGanancia = -1;
    
    if (idxCompra !== -1) {
        const compraReg = analisisArrayAsc[idxCompra];
        if (currentView === 'daily') {
            const dailyData = dataToShow;
            newIdxCompra = dailyData.findIndex(r => new Date(r.fecha).toISOString().split('T')[0] === new Date(compraReg.fecha).toISOString().split('T')[0]);
        } else {
            newIdxCompra = idxCompra;
        }
    }
    
    if (idxMaxGanancia !== -1 && idxMaxGanancia !== idxCompra) {
        const maxReg = analisisArrayAsc[idxMaxGanancia];
        if (currentView === 'daily') {
            const dailyData = dataToShow;
            newIdxMaxGanancia = dailyData.findIndex(r => new Date(r.fecha).toISOString().split('T')[0] === new Date(maxReg.fecha).toISOString().split('T')[0]);
        } else {
            newIdxMaxGanancia = idxMaxGanancia;
        }
    }
    
    container.innerHTML = '';
    
    // Crear el gráfico
    chart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: 500,
        layout: { background: { color: '#ffffff' }, textColor: '#333' },
        grid: { vertLines: { color: '#f0f0f0' }, horzLines: { color: '#f0f0f0' } },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        rightPriceScale: { borderColor: '#d1d4dc', autoScale: true, scaleMargins: { top: 0.1, bottom: 0.1 } },
        timeScale: { borderColor: '#d1d4dc', timeVisible: true, secondsVisible: false }
    });
    
    // Preparar datos para la línea de precio
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
    
    // Ajustar escala automáticamente a los datos
    chart.timeScale().fitContent();
    
    // Preparar marcadores de colores según el caso
    const markers = [];
    for (let i = 0; i < dataToShow.length; i++) {
        const a = dataToShow[i];
        const time = Math.floor(new Date(a.fecha).getTime() / 1000);
        const markerColor = getColorForCaso(a.caso_numero);
        
        markers.push({ 
            time: time, 
            position: 'aboveBar', 
            color: markerColor, 
            shape: 'circle', 
            size: 1,
            text: getTextForCaso(a.caso_numero)
        });
    }
    
    // Añadir marcador especial para COMPRA
    if (newIdxCompra !== -1) {
        const compraReg = dataToShow[newIdxCompra];
        const compraTime = Math.floor(new Date(compraReg.fecha).getTime() / 1000);
        markers.push({ 
            time: compraTime, 
            position: 'aboveBar', 
            color: '#1e7e34', 
            shape: 'arrowUp', 
            text: '🔴 COMPRA', 
            size: 2 
        });
    }
    
    // Añadir marcador especial para MÁXIMO BENEFICIO
    if (newIdxMaxGanancia !== -1 && newIdxMaxGanancia !== newIdxCompra) {
        const maxReg = dataToShow[newIdxMaxGanancia];
        const maxTime = Math.floor(new Date(maxReg.fecha).getTime() / 1000);
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
    
    // Crear leyenda de colores
    crearLeyenda(container);
    
    window.addEventListener('resize', () => { 
        if (chart) chart.applyOptions({ width: container.clientWidth }); 
    });
}

function crearLeyenda(container) {
    const legendDiv = document.createElement('div');
    legendDiv.style.cssText = `
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        padding: 12px 16px;
        background: #f8f9fa;
        border-radius: 12px;
        margin-bottom: 16px;
        font-size: 0.7rem;
        border: 1px solid #e9ecef;
    `;
    
    const items = [
        { color: COLOR_CASO[1], text: 'Caso 1 - Compra Inmediata' },
        { color: COLOR_CASO[2], text: 'Caso 2 - Compra Anticipada' },
        { color: COLOR_CASO[3], text: 'Caso 3 - Rebote corto' },
        { color: COLOR_CASO[4], text: 'Caso 4 - Compra Consolidada' },
        { color: COLOR_CASO[5], text: 'Caso 5 - Agotamiento' },
        { color: COLOR_CASO[6], text: 'Caso 6 - Compra Rápida' },
        { color: COLOR_CASO[7], text: 'Caso 7 - Pre-Compra' },
        { color: COLOR_CASO.sin_senal, text: 'Sin señal' },
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
    
    // Insertar leyenda al principio del contenedor
    container.insertBefore(legendDiv, container.firstChild);
}

function cambiarVista(tipo) {
    currentView = tipo;
    if (currentData) {
        // Necesitamos volver a calcular índices
        const primeraCompra = encontrarPrimeraCompraEnDatos(currentData);
        let idxCompra = -1;
        let idxMaxGanancia = -1;
        
        if (primeraCompra) {
            idxCompra = currentData.findIndex(r => r.fecha === primeraCompra.fecha && r.precio_cierre === primeraCompra.precio_cierre);
            const acciones = 10000 / primeraCompra.precio_cierre;
            const maxGananciaInfo = encontrarMaximoGananciaEnDatos(currentData, primeraCompra.precio_cierre, Math.floor(acciones), 10000, idxCompra);
            if (maxGananciaInfo) idxMaxGanancia = maxGananciaInfo.idx;
        }
        
        crearGrafica(currentData, idxCompra, idxMaxGanancia);
    }
}

// Funciones auxiliares (necesitan acceso a las funciones del index)
function encontrarPrimeraCompraEnDatos(analisisArrayAsc) {
    for (let i = 0; i < analisisArrayAsc.length; i++) {
        const registro = analisisArrayAsc[i];
        if (CASOS_COMPRA_REAL.includes(registro.caso_numero)) {
            if (i === 0) return registro;
            const anterior = analisisArrayAsc[i - 1];
            if (anterior && !CASOS_COMPRA_REAL.includes(anterior.caso_numero)) {
                return registro;
            }
        }
    }
    return analisisArrayAsc.find(r => CASOS_COMPRA_REAL.includes(r.caso_numero)) || null;
}

function encontrarMaximoGananciaEnDatos(analisisArrayAsc, precioCompra, acciones, dineroInvertir, idxCompra) {
    if (!precioCompra || !acciones || acciones === 0) return null;
    let maxGanancia = -Infinity;
    let idxMax = idxCompra;
    
    for (let i = idxCompra; i < analisisArrayAsc.length; i++) {
        const resultadoBruto = (analisisArrayAsc[i].precio_cierre - precioCompra) * acciones;
        const comisionCompra = 11 + (dineroInvertir * 0.004);
        const comisionVenta = 11 + (analisisArrayAsc[i].precio_cierre * acciones * 0.004);
        const resultado = resultadoBruto - (comisionCompra + comisionVenta);
        if (resultado > maxGanancia) {
            maxGanancia = resultado;
            idxMax = i;
        }
    }
    return { idx: idxMax, ganancia: maxGanancia, precio: analisisArrayAsc[idxMax].precio_cierre };
}

function limpiarGrafica() {
    if (chart) { chart = null; }
}
