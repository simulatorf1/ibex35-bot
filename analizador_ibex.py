import yfinance as yf
import pandas as pd
import numpy as np
from supabase import create_client, Client
from datetime import datetime, timezone
import time
import os

# ============================================
# CONFIGURACIÓN DE SUPABASE
# ============================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: No se encontraron las variables SUPABASE_URL o SUPABASE_KEY")
    exit(1)
    
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================
# LISTA DE EMPRESAS DEL IBEX35
# ============================================
EMPRESAS = [
    ("SAN.MC", "Banco Santander"),
    ("BBVA.MC", "BBVA"),
    ("TEF.MC", "Telefónica"),
    ("ITX.MC", "Inditex"),
    ("IBE.MC", "Iberdrola"),
    ("REP.MC", "Repsol"),
    ("FER.MC", "Ferrovial"),
    ("ENG.MC", "Enagás"),
    ("ACS.MC", "ACS"),
    ("ANA.MC", "Acciona"),
    ("CABK.MC", "CaixaBank"),
    ("MTS.MC", "ArcelorMittal"),
    ("CLNX.MC", "Cellnex"),
    ("GRF.MC", "Grifols"),
    ("AENA.MC", "Aena"),
    ("IAG.MC", "IAG"),
    ("MEL.MC", "Melia Hotels"),
    ("NTGY.MC", "Naturgy"),
    ("RED.MC", "Redeia"),
    ("ELE.MC", "Endesa"),
    ("SLR.MC", "Solaria"),
    ("UNI.MC", "Unicaja"),
    ("MAP.MC", "Mapfre"),
    ("LOG.MC", "Logista"),
    ("SGRE.MC", "Siemens Gamesa"),
    ("PHM.MC", "PharmaMar"),
    ("TRE.MC", "Técnicas Reunidas"),
    ("SAB.MC", "Banco Sabadell"),
    ("BKT.MC", "Bankinter"),
    ("ADX.MC", "Audax"),
]

def calcular_smi_rapido(high, low, close):
    """Calcula SOLO la línea RÁPIDA del SMI"""
    length_k = 10
    length_d = 3
    smooth_period = 5
    
    hh = high.rolling(window=length_k).max()
    ll = low.rolling(window=length_k).min()
    diff = hh - ll
    
    rdiff = close - (hh + ll) / 2
    
    avgrel = rdiff.ewm(span=length_d, adjust=False).mean()
    avgdiff = diff.ewm(span=length_d, adjust=False).mean()
    
    avgdiff_safe = avgdiff.replace(0, np.nan)
    smi_raw = (avgrel / (avgdiff_safe / 2)) * 100
    smi_raw = smi_raw.clip(-100, 100)
    
    smi_rapido = smi_raw.rolling(window=smooth_period).mean()
    
    return smi_rapido

def obtener_smi_con_pendiente(ticker, period, interval):
    """Obtiene el SMI y su pendiente para un periodo e intervalo dado"""
    try:
        stock = yf.Ticker(ticker)
        datos = stock.history(period=period, interval=interval)
        
        if datos.empty or len(datos) < 10:
            return None, None, False
        
        smi = calcular_smi_rapido(datos['High'], datos['Low'], datos['Close'])
        smi_clean = smi.dropna()
        
        if len(smi_clean) < 2:
            return None, None, False
        
        ultimo = round(smi_clean.iloc[-1], 2)
        penultimo = smi_clean.iloc[-2]
        pendiente = round(ultimo - penultimo, 2)
        giro_positivo = pendiente > 0
        
        return ultimo, pendiente, giro_positivo
    
    except Exception as e:
        print(f"  Error SMI: {e}")
        return None, None, False

def obtener_smi_4h(ticker):
    """Obtiene SMI cada 4 horas"""
    try:
        stock = yf.Ticker(ticker)
        # 4 horas = 4h
        datos = stock.history(period="10d", interval="4h")
        
        if datos.empty or len(datos) < 5:
            return None
        
        smi_temp = calcular_smi_rapido(datos['High'], datos['Low'], datos['Close'])
        smi_clean = smi_temp.dropna()
        
        if not smi_clean.empty:
            return round(smi_clean.iloc[-1], 2)
        
        return None
    
    except Exception as e:
        print(f"  Error SMI 4h: {e}")
        return None

def obtener_smi_semanal(ticker):
    """Obtiene SMI semanal (contexto)"""
    try:
        stock = yf.Ticker(ticker)
        datos = stock.history(period="1y", interval="1wk")
        
        if datos.empty or len(datos) < 5:
            return None
        
        smi_temp = calcular_smi_rapido(datos['High'], datos['Low'], datos['Close'])
        smi_clean = smi_temp.dropna()
        
        if not smi_clean.empty:
            return round(smi_clean.iloc[-1], 2)
        
        return None
    
    except Exception as e:
        print(f"  Error SMI semanal: {e}")
        return None

def detectar_pinchos(ticker):
    """
    Detecta pinchos alcistas y bajistas en las últimas 90 velas
    Pincho alcista: (cierre - mínimo) / mínimo > 0.05 (recuperación >5%)
    Pincho bajista: (máximo - cierre) / cierre > 0.05 (caída >5%)
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="90d", interval="1d")
        
        if hist.empty or len(hist) < 10:
            return [], []
        
        UMBRAL = 0.05  # 5%
        
        pinchos_alcistas = []
        pinchos_bajistas = []
        
        for idx, row in hist.iterrows():
            minimo = row['Low']
            maximo = row['High']
            cierre = row['Close']
            fecha = idx.strftime('%d/%m/%Y')
            
            # Pincho alcista (recuperación desde mínimo)
            recuperacion = (cierre - minimo) / minimo
            if recuperacion > UMBRAL:
                pinchos_alcistas.append({
                    "fecha": fecha,
                    "precio": round(minimo, 3),
                    "porcentaje": round(recuperacion * 100, 2)
                })
            
            # Pincho bajista (caída desde máximo)
            caida = (maximo - cierre) / cierre
            if caida > UMBRAL:
                pinchos_bajistas.append({
                    "fecha": fecha,
                    "precio": round(maximo, 3),
                    "porcentaje": round(caida * 100, 2)
                })
        
        return pinchos_alcistas, pinchos_bajistas
    
    except Exception as e:
        print(f"  Error detectando pinchos: {e}")
        return [], []

def detectar_gaps(ticker):
    """
    Detecta gaps REALES comparando máximos y mínimos entre velas consecutivas
    Gap alcista: min_actual > max_anterior
    Gap bajista: max_actual < min_anterior
    Estado del gap:
        - ABIERTO: nunca se ha tocado el rango
        - CERRADO PARCIALMENTE: se ha tocado pero no se ha rellenado entero
        - CERRADO TOTALMENTE: se ha rellenado completamente
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="90d", interval="1d")
        
        if hist.empty or len(hist) < 5:
            return [], []
        
        UMBRAL_PORCENTAJE = 1.0  # 1% mínimo para considerar un gap relevante
        
        gaps_alcistas = []
        gaps_bajistas = []
        
        for i in range(1, len(hist)):
            max_anterior = hist.iloc[i-1]['High']
            min_anterior = hist.iloc[i-1]['Low']
            min_actual = hist.iloc[i]['Low']
            max_actual = hist.iloc[i]['High']
            fecha_actual = hist.index[i].strftime('%d/%m/%Y')
            fecha_anterior = hist.index[i-1].strftime('%d/%m/%Y')
            
            # ============================================
            # GAP ALCISTA (min_actual > max_anterior)
            # ============================================
            if min_actual > max_anterior:
                diferencia = min_actual - max_anterior
                porcentaje = (diferencia / max_anterior) * 100
                
                if porcentaje >= UMBRAL_PORCENTAJE:
                    estado = "ABIERTO"
                    fecha_estado = None
                    nivel_cierre = None
                    tope_parcial = None
                    
                    for j in range(i+1, len(hist)):
                        precio_min = hist.iloc[j]['Low']
                        
                        if precio_min <= max_anterior:
                            estado = "CERRADO TOTALMENTE"
                            fecha_estado = hist.index[j].strftime('%d/%m/%Y')
                            nivel_cierre = max_anterior
                            break
                        elif precio_min < min_actual and estado == "ABIERTO":
                            estado = "CERRADO PARCIALMENTE"
                            fecha_estado = hist.index[j].strftime('%d/%m/%Y')
                            tope_parcial = round(precio_min, 3)
                    
                    gaps_alcistas.append({
                        "fecha": fecha_actual,
                        "fecha_anterior": fecha_anterior,
                        "desde": round(max_anterior, 3),
                        "hasta": round(min_actual, 3),
                        "porcentaje": round(porcentaje, 2),
                        "estado": estado,
                        "fecha_estado": fecha_estado,
                        "nivel_cierre": nivel_cierre,
                        "tope_parcial": tope_parcial
                    })
            
            # ============================================
            # GAP BAJISTA (max_actual < min_anterior)
            # ============================================
            elif max_actual < min_anterior:
                diferencia = min_anterior - max_actual
                porcentaje = (diferencia / min_anterior) * 100
                
                if porcentaje >= UMBRAL_PORCENTAJE:
                    estado = "ABIERTO"
                    fecha_estado = None
                    nivel_cierre = None
                    tope_parcial = None
                    
                    for j in range(i+1, len(hist)):
                        precio_max = hist.iloc[j]['High']
                        
                        if precio_max >= min_anterior:
                            estado = "CERRADO TOTALMENTE"
                            fecha_estado = hist.index[j].strftime('%d/%m/%Y')
                            nivel_cierre = min_anterior
                            break
                        elif precio_max > max_actual and estado == "ABIERTO":
                            estado = "CERRADO PARCIALMENTE"
                            fecha_estado = hist.index[j].strftime('%d/%m/%Y')
                            tope_parcial = round(precio_max, 3)
                    
                    gaps_bajistas.append({
                        "fecha": fecha_actual,
                        "fecha_anterior": fecha_anterior,
                        "desde": round(min_anterior, 3),
                        "hasta": round(max_actual, 3),
                        "porcentaje": round(porcentaje, 2),
                        "estado": estado,
                        "fecha_estado": fecha_estado,
                        "nivel_cierre": nivel_cierre,
                        "tope_parcial": tope_parcial
                    })
        
        return gaps_alcistas, gaps_bajistas
    
    except Exception as e:
        print(f"  Error detectando gaps: {e}")
        return [], []

def identificar_niveles(ticker, precio_actual):
    """
    Identifica SOPORTES y RESISTENCIAS con tolerancia 0.6%
    Cuenta toques TOTALES (mínimos y máximos en la misma zona)
    Muestra el RANGO REAL (mínimo y máximo de la zona)
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="90d", interval="1d")
        
        if hist.empty or len(hist) < 20:
            return [], []
        
        TOLERANCIA = 0.006  # 0.6%
        
        # ============================================
        # RECOPILAR TODOS LOS PRECIOS (mínimos y máximos)
        # ============================================
        todos_los_precios = []
        
        for i in range(len(hist)):
            fila = hist.iloc[i]
            minimo = round(fila['Low'], 3)
            maximo = round(fila['High'], 3)
            todos_los_precios.append(minimo)
            todos_los_precios.append(maximo)
        
        # ============================================
        # AGRUPAR POR ZONA (tolerancia 0.6%)
        # ============================================
        def agrupar_por_zona(precios):
            grupos = []
            usado = [False] * len(precios)
            
            for i in range(len(precios)):
                if usado[i]:
                    continue
                
                grupo = [precios[i]]
                usado[i] = True
                
                for j in range(len(precios)):
                    if not usado[j]:
                        for precio_grupo in grupo:
                            if abs(precios[j] - precio_grupo) / precio_grupo < TOLERANCIA:
                                grupo.append(precios[j])
                                usado[j] = True
                                break
                
                if len(grupo) >= 2:
                    grupos.append({
                        "minimo": min(grupo),
                        "maximo": max(grupo),
                        "toques": len(grupo),
                        "precios": grupo
                    })
            
            # Ordenar por número de toques (de mayor a menor)
            grupos.sort(key=lambda x: x["toques"], reverse=True)
            return grupos
        
        todos_los_grupos = agrupar_por_zona(todos_los_precios)
        
        # ============================================
        # CLASIFICAR POR PRECIO ACTUAL
        # ============================================
        soportes = []
        resistencias = []
        
        for g in todos_los_grupos:
            # Si el grupo está por DEBAJO del precio actual → es SOPORTE
            if g["maximo"] < precio_actual:
                soportes.append({
                    "minimo": g["minimo"],
                    "maximo": g["maximo"],
                    "toques": g["toques"],
                    "rango": f"{g['minimo']}-{g['maximo']}"
                })
            # Si el grupo está por ENCIMA del precio actual → es RESISTENCIA
            elif g["minimo"] > precio_actual:
                resistencias.append({
                    "minimo": g["minimo"],
                    "maximo": g["maximo"],
                    "toques": g["toques"],
                    "rango": f"{g['minimo']}-{g['maximo']}"
                })
            # Si el grupo contiene el precio actual, se ignora (no es ni soporte ni resistencia)
        
        # Ordenar soportes: de más cercanos a más lejanos (por el máximo del grupo)
        soportes.sort(key=lambda x: x["maximo"], reverse=True)
        
        # Ordenar resistencias: de más cercanas a más lejanas (por el mínimo del grupo)
        resistencias.sort(key=lambda x: x["minimo"])
        
        return soportes, resistencias
    
    except Exception as e:
        print(f"  Error identificando niveles: {e}")
        return [], []

def evaluar_caso(smi_4h, smi_diario, pendiente_diaria):
    """
    Evalúa cuál de los 5 casos se cumple según:
    - SMI 4h en sobreventa (< -40)
    - Estado del SMI diario
    - Pendiente del SMI diario
    """
    SOBREVENTA = -40
    SOBRECOMPRA = 40
    
    # Solo evaluamos si SMI 4h está en sobreventa
    if smi_4h is None or smi_4h >= SOBREVENTA:
        return None, "SMI 4h NO en sobreventa - SE IGNORA"
    
    # CASO 1: SMI diario en sobreventa + pendiente positiva
    if smi_diario is not None and smi_diario < SOBREVENTA and pendiente_diaria:
        return 1, "COMPRA YA (diario sobreventa + pendiente positiva)"
    
    # CASO 2: SMI diario en sobreventa + pendiente negativa
    if smi_diario is not None and smi_diario < SOBREVENTA and not pendiente_diaria:
        return 2, "COMPRA CON RIESGO (diario sobreventa pero pendiente negativa)"
    
    # CASO 3: SMI diario normal (<40 y >-40) + pendiente negativa
    if smi_diario is not None and -40 <= smi_diario <= 40 and not pendiente_diaria:
        return 3, "REBOTE CORTO (tendencia bajista, solo rebote)"
    
    # CASO 4: SMI diario normal (<40 y >-40) + pendiente positiva
    if smi_diario is not None and -40 <= smi_diario <= 40 and pendiente_diaria:
        return 4, "SUBIDA (ojo resistencias)"
    
    # CASO 5: SMI diario en sobrecompra (>40)
    if smi_diario is not None and smi_diario > SOBRECOMPRA:
        return 5, "ÚLTIMA SUBIDA (antes de vender)"
    
    # Por defecto si no encaja en ninguno
    return None, "Sin caso definido"

def guardar_recomendacion(ticker, nombre, precio, smi_4h, smi_diario, smi_semanal, caso, mensaje, pendiente_diaria):
    """Guarda la recomendación en Supabase"""
    try:
        fecha_actual = datetime.now(timezone.utc).isoformat()
        
        data = {
            "fecha": fecha_actual,
            "ticker": ticker,
            "nombre_empresa": nombre,
            "precio_cierre": precio,
            "smi_4h": smi_4h if smi_4h else None,
            "smi_diario": smi_diario,
            "smi_semanal": smi_semanal if smi_semanal else None,
            "pendiente_diaria": pendiente_diaria,
            "caso": caso,
            "recomendacion": mensaje
        }
        
        supabase.table("recomendaciones_ibex").insert(data).execute()
        
    except Exception as e:
        print(f"  ❌ Error guardando: {e}")

def analizar_todo():
    """Analiza todas las empresas con la nueva lógica de SMI 4h"""
    print(f"🚀 Iniciando análisis - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)
    print("📊 NUEVA LÓGICA - SMI 4h como GATILLO:")
    print("   1. SMI 4h < -40 (sobreventa) → condicional")
    print("   2. Si no se cumple → SE IGNORA (sin análisis)")
    print("   3. Según SMI diario y su pendiente → 5 CASOS")
    print("=" * 70)
    print("📊 RESISTENCIAS, SOPORTES, GAPS Y PINCHOS como CONTEXTO")
    print("=" * 70)
    
    contador_casos = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    
    for ticker, nombre in EMPRESAS:
        print(f"\n{'='*60}")
        print(f"📊 Analizando: {nombre} ({ticker})")
        print(f"{'='*60}")
        
        # Obtener precio actual
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            precio_actual = info.get("currentPrice", info.get("regularMarketPrice"))
            if precio_actual is None:
                print(f"  ⚠️ Sin precio")
                continue
        except Exception as e:
            print(f"  ⚠️ Error precio: {e}")
            continue
        
        # Obtener SMI DIARIO (con pendiente)
        smi_diario, pendiente_diaria, giro_positivo = obtener_smi_con_pendiente(ticker, "90d", "1d")
        
        # Obtener SMI 4h (GATILLO)
        smi_4h = obtener_smi_4h(ticker)
        
        # Obtener SMI semanal (CONTEXTO)
        smi_semanal = obtener_smi_semanal(ticker)
        
        # Detectar pinchos
        pinchos_alcistas, pinchos_bajistas = detectar_pinchos(ticker)
        
        # Detectar gaps
        gaps_alcistas, gaps_bajistas = detectar_gaps(ticker)
        
        # Identificar niveles
        soportes, resistencias = identificar_niveles(ticker, precio_actual)
        
        # ============================================
        # EVALUAR CASO (SOLO si SMI 4h < -40)
        # ============================================
        caso, mensaje = evaluar_caso(smi_4h, smi_diario, giro_positivo)
        
        if caso is None:
            print(f"\n  ⚪ CONCLUSIÓN: {mensaje}")
        else:
            contador_casos[caso] += 1
            print(f"\n  🎯 CASO {caso}: {mensaje}")
        
        # ============================================
        # MOSTRAR INFORMACIÓN DE CONTEXTO
        # ============================================
        print(f"\n  📊 CONTEXTO TÉCNICO:")
        print(f"  {'='*50}")
        print(f"  💰 Precio actual: {precio_actual}€")
        print(f"  🕐 SMI 4h (GATILLO): {smi_4h} {'(SOBREVENTA ✅)' if smi_4h is not None and smi_4h < -40 else '(Normal o error)'}")
        print(f"  📅 SMI DIARIO: {smi_diario} (Pendiente: {pendiente_diaria} - {'Positiva ✅' if giro_positivo else 'Negativa ❌'})")
        print(f"  📆 SMI SEMANAL (contexto): {smi_semanal}")
        
        # Niveles más relevantes
        resistencias_por_toques = sorted(resistencias, key=lambda x: x["toques"], reverse=True)
        top_2_resistencias = resistencias_por_toques[:2]
        
        soportes_por_toques = sorted(soportes, key=lambda x: x["toques"], reverse=True)
        top_2_soportes = soportes_por_toques[:2]
        
        print(f"\n  📈 RESISTENCIAS (por encima):")
        if top_2_resistencias:
            for r in top_2_resistencias:
                recorrido = ((r["minimo"] - precio_actual) / precio_actual) * 100
                print(f"     💪 {r['rango']}€ - {r['toques']} toques (recorrido: {recorrido:.2f}%)")
        else:
            print(f"     ❌ No hay resistencias claras")
        
        print(f"\n  📉 SOPORTES (por debajo):")
        if top_2_soportes:
            for s in top_2_soportes:
                distancia = ((precio_actual - s["maximo"]) / precio_actual) * 100
                print(f"     💪 {s['rango']}€ - {s['toques']} toques (distancia: {distancia:.2f}%)")
        else:
            print(f"     ❌ No hay soportes claros")
        
        # Gaps
        print(f"\n  📊 GAPS:")
        if gaps_alcistas:
            print(f"     📈 Gaps alcistas: {len(gaps_alcistas)}")
            for g in gaps_alcistas[:2]:
                print(f"        {g['fecha']} - {g['desde']}€ → {g['hasta']}€ ({g['porcentaje']}%) - {g['estado']}")
        else:
            print(f"     📈 Gaps alcistas: 0")
        
        if gaps_bajistas:
            print(f"     📉 Gaps bajistas: {len(gaps_bajistas)}")
            for g in gaps_bajistas[:2]:
                print(f"        {g['fecha']} - {g['desde']}€ → {g['hasta']}€ ({g['porcentaje']}%) - {g['estado']}")
        else:
            print(f"     📉 Gaps bajistas: 0")
        
        # Pinchos
        print(f"\n  📊 PINCHOS:")
        if pinchos_alcistas:
            print(f"     🔺 Pinchos alcistas: {len(pinchos_alcistas)}")
            for p in pinchos_alcistas[:2]:
                print(f"        {p['fecha']} - giró en {p['precio']}€ (recuperó {p['porcentaje']}%)")
        else:
            print(f"     🔺 Pinchos alcistas: 0")
        
        if pinchos_bajistas:
            print(f"     🔻 Pinchos bajistas: {len(pinchos_bajistas)}")
            for p in pinchos_bajistas[:2]:
                print(f"        {p['fecha']} - giró en {p['precio']}€ (cayó {p['porcentaje']}%)")
        else:
            print(f"     🔻 Pinchos bajistas: 0")
        
        # Guardar en Supabase
        guardar_recomendacion(ticker, nombre, precio_actual, 
                              smi_4h, smi_diario, smi_semanal,
                              caso, mensaje, pendiente_diaria)
        
        time.sleep(0.5)
    
    print("\n" + "=" * 70)
    print(f"✅ Análisis completado")
    print(f"📊 Resumen de CASOS (cuando SMI 4h < -40):")
    print(f"   CASO 1 (COMPRA YA): {contador_casos[1]}")
    print(f"   CASO 2 (COMPRA CON RIESGO): {contador_casos[2]}")
    print(f"   CASO 3 (REBOTE CORTO): {contador_casos[3]}")
    print(f"   CASO 4 (SUBIDA): {contador_casos[4]}")
    print(f"   CASO 5 (ÚLTIMA SUBIDA): {contador_casos[5]}")
    print("=" * 70)

if __name__ == "__main__":
    analizar_todo()
