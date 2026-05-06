// Configuración - REEMPLAZA con tus datos de Supabase
const SUPABASE_URL = "https://tu-proyecto.supabase.co";
const SUPABASE_KEY = "tu-anon-key-public";

async function buscarEmpresa() {
    const input = document.getElementById('inputEmpresa').value.trim();
    const resultadoDiv = document.getElementById('resultado');
    const errorDiv = document.getElementById('error');
    
    if (!input) {
        mostrarError('Escribe un nombre de empresa');
        return;
    }
    
    resultadoDiv.classList.add('hidden');
    errorDiv.classList.add('hidden');
    
    mostrarLoading();
    
    try {
        const response = await fetch(`${SUPABASE_URL}/rest/v1/rpc/buscar_empresa`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'apikey': SUPABASE_KEY,
                'Authorization': `Bearer ${SUPABASE_KEY}`
            },
            body: JSON.stringify({ nombre_busqueda: input })
        });
        
        if (!response.ok) {
            // Si falla la función RPC, hacemos búsqueda directa
            await buscarDirecta(input);
            return;
        }
        
        const data = await response.json();
        
        if (!data || data.length === 0) {
            mostrarError('No se encontró ninguna empresa con ese nombre');
            return;
        }
        
        mostrarResultado(data[0]);
        
    } catch (error) {
        console.error('Error:', error);
        mostrarError('Error al conectar con la base de datos');
    }
}

async function buscarDirecta(nombre) {
    try {
        const response = await fetch(`${SUPABASE_URL}/rest/v1/recomendaciones_ibex?nombre_empresa=ilike.%${encodeURIComponent(nombre)}%&order=fecha.desc&limit=1`, {
            headers: {
                'apikey': SUPABASE_KEY,
                'Authorization': `Bearer ${SUPABASE_KEY}`
            }
        });
        
        if (!response.ok) throw new Error('Error en la búsqueda');
        
        const data = await response.json();
        
        if (!data || data.length === 0) {
            mostrarError('No se encontró ninguna empresa. Prueba con: Santander, BBVA, Inditex, Telefónica, Iberdrola...');
            return;
        }
        
        mostrarResultado(data[0]);
        
    } catch (error) {
        mostrarError('Error al buscar. Revisa tu conexión a Supabase');
    }
}

function mostrarResultado(dato) {
    const resultadoDiv = document.getElementById('resultado');
    
    const casosTexto = {
        1: '🔴 COMPRA YA (Señal fuerte)',
        2: '🟡 COMPRA CON RIESGO',
        3: '🔵 REBOTE CORTO (Tendencia bajista)',
        4: '🟢 SUBIDA (Ojo resistencias)',
        5: '⚡ ÚLTIMA SUBIDA (Antes de vender)'
    };
    
    const pendienteTexto = dato.pendiente_diaria > 0 ? '✅ Positiva' : '❌ Negativa';
    const pendienteClase = dato.pendiente_diaria > 0 ? 'positivo' : 'negativo';
    
    const smi4hClase = dato.smi_4h < -40 ? 'positivo' : '';
    const smiDiarioClase = dato.smi_diario < -40 ? 'positivo' : (dato.smi_diario > 40 ? 'negativo' : '');
    
    let html = `
        <div class="caso-tag caso-${dato.caso}">${casosTexto[dato.caso] || 'Sin clasificación'}</div>
        
        <div class="info-grid">
            <div class="info-card">
                <h3>🏢 Empresa</h3>
                <div class="valor">${dato.nombre_empresa}</div>
                <small>${dato.ticker}</small>
            </div>
            <div class="info-card">
                <h3>💰 Precio</h3>
                <div class="valor">${dato.precio_cierre}€</div>
            </div>
            <div class="info-card">
                <h3>📅 Fecha</h3>
                <div class="valor">${new Date(dato.fecha).toLocaleString()}</div>
            </div>
        </div>
        
        <div class="info-grid">
            <div class="info-card">
                <h3>🕐 SMI 4h (Gatillo)</h3>
                <div class="valor ${smi4hClase}">${dato.smi_4h ?? 'N/A'}</div>
                ${dato.smi_4h < -40 ? '<small>✅ Sobreventa activada</small>' : '<small>No hay señal 4h</small>'}
            </div>
            <div class="info-card">
                <h3>📈 SMI Diario</h3>
                <div class="valor ${smiDiarioClase}">${dato.smi_diario ?? 'N/A'}</div>
                <small>Pendiente: <span class="${pendienteClase}">${pendienteTexto}</span> (${dato.pendiente_diaria})</small>
            </div>
            <div class="info-card">
                <h3>📆 SMI Semanal</h3>
                <div class="valor">${dato.smi_semanal ?? 'N/A'}</div>
                <small>Contexto</small>
            </div>
        </div>
        
        <div class="seccion">
            <h3>📊 RECOMENDACIÓN</h3>
            <p style="font-size: 1.1rem; line-height: 1.5;">${dato.recomendacion || 'Sin recomendación específica'}</p>
        </div>
    `;
    
    resultadoDiv.innerHTML = html;
    resultadoDiv.classList.remove('hidden');
}

function mostrarLoading() {
    const resultadoDiv = document.getElementById('resultado');
    resultadoDiv.innerHTML = '<div class="info-card" style="text-align: center;">🔄 Cargando datos...</div>';
    resultadoDiv.classList.remove('hidden');
}

function mostrarError(mensaje) {
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = mensaje;
    errorDiv.classList.remove('hidden');
    document.getElementById('resultado').classList.add('hidden');
}

// Eventos
document.getElementById('btnBuscar').addEventListener('click', buscarEmpresa);
document.getElementById('inputEmpresa').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') buscarEmpresa();
});
