// ============================================
// CONFIGURACIÓN DE SUPABASE
// ============================================
const SUPABASE_URL = "https://klwcletpqqsabtdanldx.supabase.co";
const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtsd2NsZXRwcXFzYWJ0ZGFubGR4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY4MDg2NTEsImV4cCI6MjA5MjM4NDY1MX0.nbs0tYbFOL-I8qIkgB7Ub_jcOwHTdzg0EcAp1DS6sCU";

// Casos que consideramos "señal" (todos excepto null)
const CASOS_SEÑAL = [1, 2, 3, 4, 5, 6, 7];

// Textos para cada caso
const CASOS_TEXTO = {
    1: '🔴 CASO 1: COMPRA YA',
    2: '🟠 CASO 2: COMPRA CON RIESGO',
    3: '🔵 CASO 3: REBOTE CORTO',
    4: '🟢 CASO 4: SUBIDA',
    5: '⚪ CASO 5: ÚLTIMA SUBIDA',
    6: '🟣 CASO 6: COMPRA INMEDIATA',
    7: '🟤 CASO 7: A PUNTO DE COMPRA'
};

// ============================================
// CARGAR EMPRESAS CON SEÑAL
// ============================================
async function cargarSeñales() {
    const listaDiv = document.getElementById('listaSeñales');
    
    if (!listaDiv) {
        console.error('No se encontró el elemento listaSeñales');
        return;
    }
    
    try {
        const response = await fetch(`${SUPABASE_URL}/rest/v1/recomendaciones_ibex?select=*&order=fecha.desc&limit=200`, {
            headers: {
                'apikey': SUPABASE_KEY,
                'Authorization': `Bearer ${SUPABASE_KEY}`
            }
        });
        
        if (!response.ok) throw new Error('Error cargando empresas');
        
        const todosLosAnalisis = await response.json();
        
        // Agrupar por ticker y quedarse con el último
        const ultimosAnalisis = {};
        for (const analisis of todosLosAnalisis) {
            const ticker = analisis.ticker;
            if (!ultimosAnalisis[ticker] || new Date(analisis.fecha) > new Date(ultimosAnalisis[ticker].fecha)) {
                ultimosAnalisis[ticker] = analisis;
            }
        }
        
        // Filtrar solo los que tienen caso de señal
        const casosSeñal = Object.values(ultimosAnalisis).filter(a => CASOS_SEÑAL.includes(a.caso_numero));
        
        // Ordenar por caso (prioridad 1,2,6,7,3,4,5)
        casosSeñal.sort((a, b) => {
            const orden = [1, 2, 6, 7, 3, 4, 5];
            return orden.indexOf(a.caso_numero) - orden.indexOf(b.caso_numero);
        });
        
        mostrarSeñales(casosSeñal);
        
    } catch (error) {
        console.error('Error:', error);
        listaDiv.innerHTML = '<div class="sin-señales">❌ Error al cargar las señales</div>';
    }
}

// ============================================
// MOSTRAR TARJETAS DE SEÑALES
// ============================================
function mostrarSeñales(empresas) {
    const listaDiv = document.getElementById('listaSeñales');
    
    if (!listaDiv) return;
    
    if (empresas.length === 0) {
        listaDiv.innerHTML = '<div class="sin-señales">📭 No hay empresas con señal en este momento</div>';
        return;
    }
    
    let html = '';
    for (const emp of empresas) {
        const pendienteClase = emp.pendiente_diaria > 0 ? 'positivo' : 'negativo';
        const pendienteSimbolo = emp.pendiente_diaria > 0 ? '▲' : '▼';
        const fechaFormateada = new Date(emp.fecha).toLocaleString('es-ES', { timeZone: 'Europe/Madrid' });
        const tipoSenal = emp.tipo_señal || (emp.activada_por_4h ? 'GATILLO 4h' : 'DIRECTA DIARIO');
        
        html += `
            <div class="tarjeta-empresa" onclick="verDetalle('${emp.ticker}')">
                <div class="tarjeta-header">
                    <div>
                        <span class="tarjeta-nombre">${emp.nombre_empresa}</span>
                        <span class="tarjeta-ticker">${emp.ticker}</span>
                    </div>
                    <span class="caso-badge badge-caso-${emp.caso_numero}">${CASOS_TEXTO[emp.caso_numero]}</span>
                </div>
                <div class="tarjeta-precio">${emp.precio_cierre} €</div>
                <div class="tarjeta-smis">
                    <span class="smi-4h">SMI 4h: ${emp.smi_4h ?? 'N/A'}</span>
                    <span class="smi-diario">SMI diario: ${emp.smi_diario ?? 'N/A'}</span>
                    <span class="${pendienteClase}">${pendienteSimbolo} ${Math.abs(emp.pendiente_diaria || 0)}</span>
                </div>
                <div class="tipo-senal">📌 ${tipoSenal}</div>
                <div class="tarjeta-fecha">
                    📅 ${fechaFormateada}
                </div>
            </div>
        `;
    }
    
    listaDiv.innerHTML = html;
}

// ============================================
// VER DETALLE DE EMPRESA CON HISTORIAL
// ============================================
async function verDetalle(ticker) {
    const seccionSeñales = document.getElementById('seccionSeñales');
    const resultadoDiv = document.getElementById('resultadoDetalle');
    
    if (!seccionSeñales || !resultadoDiv) return;
    
    seccionSeñales.classList.add('hidden');
    resultadoDiv.classList.remove('hidden');
    resultadoDiv.classList.add('resultado-detalle');
    resultadoDiv.innerHTML = '<div class="loading">🔄 Cargando datos...</div>';
    
    try {
        const response = await fetch(`${SUPABASE_URL}/rest/v1/recomendaciones_ibex?ticker=eq.${encodeURIComponent(ticker)}&order=fecha.desc&limit=30`, {
            headers: {
                'apikey': SUPABASE_KEY,
                'Authorization': `Bearer ${SUPABASE_KEY}`
            }
        });
        
        if (!response.ok) throw new Error('Error cargando detalle');
        
        const data = await response.json();
        
        if (data && data.length > 0) {
            mostrarDetalleConHistorial(data);
        } else {
            resultadoDiv.innerHTML = '<div class="error">No se encontraron datos</div>';
        }
        
    } catch (error) {
        resultadoDiv.innerHTML = `<div class="error">❌ Error: ${error.message}</div>`;
    }
}

// ============================================
// FORMATEAR LISTA
// ============================================
function formatearLista(texto) {
    if (!texto) return '<div class="item">No hay datos</div>';
    const lineas = texto.split('\n');
    return lineas.map(linea => `<div class="item">📌 ${linea}</div>`).join('');
}

// ============================================
// MOSTRAR DETALLE COMPLETO CON HISTORIAL
// ============================================
function mostrarDetalleConHistorial(analisisArray) {
    const resultadoDiv = document.getElementById('resultadoDetalle');
    if (!resultadoDiv) return;
    
    const ultimo = analisisArray[0];
    
    const pendienteClase = ultimo.pendiente_diaria > 0 ? 'positivo-texto' : 'negativo-texto';
    const pendienteTexto = ultimo.pendiente_diaria > 0 ? '▲ Positiva' : '▼ Negativa';
    const smi4hClase = ultimo.smi_4h < -40 ? 'positivo-texto' : '';
    const fechaFormateada = new Date(ultimo.fecha).toLocaleString('es-ES', { timeZone: 'Europe/Madrid' });
    
    // Generar tabla de historial
    let historialHtml = `
        <div class="seccion">
            <h3>📜 HISTORIAL DE ANÁLISIS (Últimos ${analisisArray.length})</h3>
            <div class="scroll-horizontal">
                <table class="tabla-historial">
                    <thead>
                        <tr>
                            <th>Fecha</th>
                            <th>Precio</th>
                            <th>SMI 4h</th>
                            <th>SMI Diario</th>
                            <th>Pendiente</th>
                            <th>Caso</th>
                            <th>Tipo Señal</th>
                            <th>Recomendación</th>
                        </tr>
                    </thead>
                    <tbody>
    `;
    
    for (const a of analisisArray) {
        const fecha = new Date(a.fecha).toLocaleString('es-ES', { timeZone: 'Europe/Madrid' });
        const casoClase = `historial-caso-${a.caso_numero || 0}`;
        const pendienteSimbolo = a.pendiente_diaria > 0 ? '▲' : (a.pendiente_diaria < 0 ? '▼' : '●');
        const tipoSenal = a.tipo_señal || (a.activada_por_4h ? 'GATILLO 4h' : 'DIRECTA');
        
        let casoTexto = '';
        if (a.caso_numero === 1) casoTexto = '🔴 CASO 1';
        else if (a.caso_numero === 2) casoTexto = '🟠 CASO 2';
        else if (a.caso_numero === 3) casoTexto = '🔵 CASO 3';
        else if (a.caso_numero === 4) casoTexto = '🟢 CASO 4';
        else if (a.caso_numero === 5) casoTexto = '⚪ CASO 5';
        else if (a.caso_numero === 6) casoTexto = '🟣 CASO 6';
        else if (a.caso_numero === 7) casoTexto = '🟤 CASO 7';
        else casoTexto = '⚪ SIN SEÑAL';
        
        historialHtml += `
            <tr class="${casoClase}">
                <td>${fecha}</td>
                <td><strong>${a.precio_cierre}€</strong></td>
                <td>${a.smi_4h ?? 'N/A'}</td>
                <td>${a.smi_diario ?? 'N/A'}</td>
                <td>${pendienteSimbolo} ${Math.abs(a.pendiente_diaria || 0)}</td>
                <td>${casoTexto}</td>
                <td>${tipoSenal}</td>
                <td style="max-width: 200px; white-space: normal;">${a.recomendacion ? a.recomendacion.substring(0, 60) + '...' : '-'}</td>
            </tr>
        `;
    }
    
    historialHtml += `
                    </tbody>
                </table>
            </div>
        </div>
    `;
    
    let html = `
        <button class="btn-cerrar" onclick="cerrarDetalle()">← Volver a señales</button>
        
        <div class="caso-tag caso-${ultimo.caso_numero}">${CASOS_TEXTO[ultimo.caso_numero]}</div>
        
        <div class="info-grid">
            <div class="info-card">
                <h3>🏢 Empresa</h3>
                <div class="valor">${ultimo.nombre_empresa}</div>
                <div class="small">${ultimo.ticker}</div>
            </div>
            <div class="info-card">
                <h3>💰 Precio Actual</h3>
                <div class="valor">${ultimo.precio_cierre} €</div>
                <div class="small">Último cierre</div>
            </div>
            <div class="info-card">
                <h3>📅 Último análisis</h3>
                <div class="valor">${fechaFormateada}</div>
                <div class="small">Hora España</div>
            </div>
        </div>
        
        <div class="info-grid">
            <div class="info-card">
                <h3>🕐 SMI 4h</h3>
                <div class="valor ${smi4hClase}">${ultimo.smi_4h ?? 'N/A'}</div>
                <div class="small">${ultimo.smi_4h < -40 ? '✅ Señal activada' : 'Sin señal'}</div>
            </div>
            <div class="info-card">
                <h3>📈 SMI Diario</h3>
                <div class="valor">${ultimo.smi_diario ?? 'N/A'}</div>
                <div class="small ${pendienteClase}">Pendiente: ${pendienteTexto}</div>
            </div>
            <div class="info-card">
                <h3>📆 SMI Semanal</h3>
                <div class="valor">${ultimo.smi_semanal ?? 'N/A'}</div>
                <div class="small">Contexto</div>
            </div>
        </div>
        
        <div class="info-grid">
            <div class="info-card">
                <h3>🏷️ Tipo de Señal</h3>
                <div class="valor">${ultimo.tipo_señal || (ultimo.activada_por_4h ? 'GATILLO 4h' : 'DIRECTA DIARIO')}</div>
                <div class="small">${ultimo.activada_por_4h ? 'Activada por SMI 4h' : 'Señal directa por diario'}</div>
            </div>
        </div>
        
        <div class="seccion">
            <h3>💡 RECOMENDACIÓN</h3>
            <div class="recomendacion-texto">${ultimo.recomendacion || 'Sin recomendación'}</div>
        </div>
    `;
    
    // Niveles
    if (ultimo.soportes || ultimo.resistencias) {
        html += `
            <div class="seccion">
                <h3>📊 NIVELES CLAVE</h3>
                <div class="grid-2col">
                    <div>
                        <h4 style="margin-bottom: 10px; color: #28a745;">📉 SOPORTES</h4>
                        <div class="lista-items">${formatearLista(ultimo.soportes)}</div>
                    </div>
                    <div>
                        <h4 style="margin-bottom: 10px; color: #dc3545;">📈 RESISTENCIAS</h4>
                        <div class="lista-items">${formatearLista(ultimo.resistencias)}</div>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Gaps
    if (ultimo.gaps_alcistas || ultimo.gaps_bajistas) {
        html += `
            <div class="seccion">
                <h3>🕳️ GAPS</h3>
                <div class="grid-2col">
                    <div>
                        <h4 style="margin-bottom: 10px; color: #28a745;">📈 Gaps Alcistas</h4>
                        <div class="lista-items">${formatearLista(ultimo.gaps_alcistas)}</div>
                    </div>
                    <div>
                        <h4 style="margin-bottom: 10px; color: #dc3545;">📉 Gaps Bajistas</h4>
                        <div class="lista-items">${formatearLista(ultimo.gaps_bajistas)}</div>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Pinchos
    if (ultimo.pinchos_alcistas || ultimo.pinchos_bajistas) {
        html += `
            <div class="seccion">
                <h3>📍 PINCHOS</h3>
                <div class="grid-2col">
                    <div>
                        <h4 style="margin-bottom: 10px; color: #28a745;">🔺 Pinchos Alcistas</h4>
                        <div class="lista-items">${formatearLista(ultimo.pinchos_alcistas)}</div>
                    </div>
                    <div>
                        <h4 style="margin-bottom: 10px; color: #dc3545;">🔻 Pinchos Bajistas</h4>
                        <div class="lista-items">${formatearLista(ultimo.pinchos_bajistas)}</div>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Añadir historial
    html += historialHtml;
    
    resultadoDiv.innerHTML = html;
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ============================================
// CERRAR DETALLE
// ============================================
function cerrarDetalle() {
    const seccionSeñales = document.getElementById('seccionSeñales');
    const resultadoDiv = document.getElementById('resultadoDetalle');
    
    if (!seccionSeñales || !resultadoDiv) return;
    
    seccionSeñales.classList.remove('hidden');
    resultadoDiv.classList.add('hidden');
    resultadoDiv.classList.remove('resultado-detalle');
    cargarSeñales();
}

// ============================================
// BUSCAR EMPRESA ESPECÍFICA
// ============================================
async function buscarEmpresa() {
    const input = document.getElementById('inputEmpresa');
    if (!input) return;
    
    const busqueda = input.value.trim();
    
    if (!busqueda) {
        cargarSeñales();
        return;
    }
    
    const seccionSeñales = document.getElementById('seccionSeñales');
    const resultadoDiv = document.getElementById('resultadoDetalle');
    
    if (!seccionSeñales || !resultadoDiv) return;
    
    seccionSeñales.classList.add('hidden');
    resultadoDiv.classList.remove('hidden');
    resultadoDiv.classList.add('resultado-detalle');
    resultadoDiv.innerHTML = '<div class="loading">🔄 Buscando...</div>';
    
    try {
        const response = await fetch(`${SUPABASE_URL}/rest/v1/recomendaciones_ibex?nombre_empresa=ilike.%25${encodeURIComponent(busqueda)}%25&order=fecha.desc&limit=30`, {
            headers: {
                'apikey': SUPABASE_KEY,
                'Authorization': `Bearer ${SUPABASE_KEY}`
            }
        });
        
        if (!response.ok) throw new Error('Error');
        
        const data = await response.json();
        
        if (!data || data.length === 0) {
            resultadoDiv.innerHTML = '<div class="error">❌ No se encontró ninguna empresa. Prueba con: Santander, BBVA, Inditex...</div><button class="btn-cerrar" onclick="cerrarDetalle()">← Volver</button>';
            return;
        }
        
        mostrarDetalleConHistorial(data);
        
    } catch (error) {
        resultadoDiv.innerHTML = `<div class="error">❌ Error: ${error.message}</div><button class="btn-cerrar" onclick="cerrarDetalle()">← Volver</button>`;
    }
}

// ============================================
// INICIALIZAR EVENTOS
// ============================================
document.addEventListener('DOMContentLoaded', function() {
    const btnBuscar = document.getElementById('btnBuscar');
    const inputEmpresa = document.getElementById('inputEmpresa');
    
    if (btnBuscar) {
        btnBuscar.addEventListener('click', buscarEmpresa);
    }
    
    if (inputEmpresa) {
        inputEmpresa.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') buscarEmpresa();
        });
    }
    
    // Cargar señales al inicio
    cargarSeñales();
});
