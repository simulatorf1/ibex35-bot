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

def obtener_smi_rapido_con_pendiente(ticker):
    """Obtiene el SMI rápido y calcula su pendiente"""
    try:
        stock = yf.Ticker(ticker)
        datos = stock.history(period="90d", interval="1d")
        
        if datos.empty or len(datos) < 10:
            return None, None, False
        
        smi_rapido = calcular_smi_rapido(datos['High'], datos['Low'], datos['Close'])
        smi_clean = smi_rapido.dropna()
        
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

def obtener_smi_horario_semanal(ticker):
    """Obtiene SMI horario y semanal"""
    try:
        stock = yf.Ticker(ticker)
        
        datos_h = stock.history(period="7d", interval="1h")
        smi_h = None
        if not datos_h.empty and len(datos_h) > 5:
            smi_h_temp = calcular_smi_rapido(datos_h['High'], datos_h['Low'], datos_h['Close'])
            smi_h_clean = smi_h_temp.dropna()
            if not smi_h_clean.empty:
                smi_h = round(smi_h_clean.iloc[-1], 2)
        
        datos_w = stock.history(period="1y", interval="1wk")
        smi_w = None
        if not datos_w.empty and len(datos_w) > 5:
            smi_w_temp = calcular_smi_rapido(datos_w['High'], datos_w['Low'], datos_w['Close'])
            smi_w_clean = smi_w_temp.dropna()
            if not smi_w_clean.empty:
                smi_w = round(smi_w_clean.iloc[-1], 2)
        
        return smi_h, smi_w
    
    except Exception as e:
        print(f"  Error horario/semanal: {e}")
        return None, None

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
        # AGRUPAR POR ZONAS (tolerancia 0.6%)
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

def guardar_recomendacion(ticker, nombre, precio, smi_h, smi_rapido, smi_w, recomendacion, precio_obj):
    """Guarda la recomendación en Supabase"""
    try:
        fecha_actual = datetime.now(timezone.utc).isoformat()
        
        data = {
            "fecha": fecha_actual,
            "ticker": ticker,
            "nombre_empresa": nombre,
            "precio_cierre": precio,
            "smi_horario": smi_h if smi_h else None,
            "smi_diario": smi_rapido,
            "smi_semanal": smi_w if smi_w else None,
            "recomendacion": recomendacion,
            "precio_objetivo": precio_obj if precio_obj else None
        }
        
        supabase.table("recomendaciones").insert(data).execute()
        
    except Exception as e:
        print(f"  ❌ Error guardando: {e}")

def analizar_todo():
    """Analiza todas las empresas con la lógica correcta"""
    print(f"🚀 Iniciando análisis - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)
    print("📊 CONDICIONES PARA COMPRA:")
    print("   1. SMI RÁPIDO < -40 (sobreventa)")
    print("   2. SMI RÁPIDO con GIRO POSITIVO (pendiente > 0)")
    print("   3. Resistencia válida a más del 3% del precio actual")
    print("=" * 70)
    
    contador_compras = 0
    contador_compras_perfectas = 0
    
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
        
        # Obtener SMI RÁPIDO
        smi_rapido, pendiente, giro_positivo = obtener_smi_rapido_con_pendiente(ticker)
        
        # Obtener SMI horario y semanal
        smi_horario, smi_semanal = obtener_smi_horario_semanal(ticker)
        
        # Detectar pinchos
        pinchos_alcistas, pinchos_bajistas = detectar_pinchos(ticker)
        
        # Detectar gaps
        gaps_alcistas, gaps_bajistas = detectar_gaps(ticker)
        
        # Identificar niveles (NUEVO: cuenta toques TOTALES)
        soportes, resistencias = identificar_niveles(ticker, precio_actual)
        
        print(f"\n  💰 Precio actual: {precio_actual}€")
        print(f"  📊 SMI RÁPIDO: {smi_rapido}")
        print(f"  📊 Pendiente: {pendiente} (Giro: {'✅' if giro_positivo else '❌'})")
        print(f"  📊 SMI HORARIO: {smi_horario}")
        
        # ============================================
        # MOSTRAR GAPS REALES
        # ============================================
        print(f"\n  📊 GAPS REALES (huecos sin cotizar):")
        print(f"  {'='*50}")
        
        print(f"  📈 Gaps alcistas (min_actual > max_anterior):")
        if gaps_alcistas:
            for g in gaps_alcistas:
                if g["estado"] == "ABIERTO":
                    print(f"     {g['fecha']} - {g['desde']}€ → {g['hasta']}€ ({g['porcentaje']}%) - 🔴 {g['estado']}")
                elif g["estado"] == "CERRADO PARCIALMENTE":
                    print(f"     {g['fecha']} - {g['desde']}€ → {g['hasta']}€ ({g['porcentaje']}%) - 🟡 {g['estado']} (llegó a {g['tope_parcial']}€ el {g['fecha_estado']})")
                else:
                    print(f"     {g['fecha']} - {g['desde']}€ → {g['hasta']}€ ({g['porcentaje']}%) - 🟢 {g['estado']} (cerró en {g['nivel_cierre']}€ el {g['fecha_estado']})")
            print(f"     Total: {len(gaps_alcistas)} gaps alcistas")
        else:
            print(f"     0")
        
        print(f"\n  📉 Gaps bajistas (max_actual < min_anterior):")
        if gaps_bajistas:
            for g in gaps_bajistas:
                if g["estado"] == "ABIERTO":
                    print(f"     {g['fecha']} - {g['desde']}€ → {g['hasta']}€ ({g['porcentaje']}%) - 🔴 {g['estado']}")
                elif g["estado"] == "CERRADO PARCIALMENTE":
                    print(f"     {g['fecha']} - {g['desde']}€ → {g['hasta']}€ ({g['porcentaje']}%) - 🟡 {g['estado']} (llegó a {g['tope_parcial']}€ el {g['fecha_estado']})")
                else:
                    print(f"     {g['fecha']} - {g['desde']}€ → {g['hasta']}€ ({g['porcentaje']}%) - 🟢 {g['estado']} (cerró en {g['nivel_cierre']}€ el {g['fecha_estado']})")
            print(f"     Total: {len(gaps_bajistas)} gaps bajistas")
        else:
            print(f"     0")
        
        # ============================================
        # MOSTRAR PINCHOS
        # ============================================
        print(f"\n  📊 PINCHOS DESTACADOS (recuperación/caída >5%):")
        print(f"  {'='*50}")
        
        print(f"  🔺 Pinchos alcistas (giro desde mínimo):")
        if pinchos_alcistas:
            for p in pinchos_alcistas:
                print(f"     {p['fecha']} - giró en {p['precio']}€ (recuperó {p['porcentaje']}%)")
            print(f"     Total: {len(pinchos_alcistas)} pinchos alcistas")
        else:
            print(f"     0")
        
        print(f"\n  🔻 Pinchos bajistas (giro desde máximo):")
        if pinchos_bajistas:
            for p in pinchos_bajistas:
                print(f"     {p['fecha']} - giró en {p['precio']}€ (cayó {p['porcentaje']}%)")
            print(f"     Total: {len(pinchos_bajistas)} pinchos bajistas")
        else:
            print(f"     0")
        
        # ============================================
        # MOSTRAR NIVELES MÁS RELEVANTES
        # ============================================
        # Seleccionar los 2 con más toques de cada lado
        resistencias_por_toques = sorted(resistencias, key=lambda x: x["toques"], reverse=True)
        top_2_resistencias = resistencias_por_toques[:2]
        
        soportes_por_toques = sorted(soportes, key=lambda x: x["toques"], reverse=True)
        top_2_soportes = soportes_por_toques[:2]
        
        print(f"\n  📊 NIVELES MÁS RELEVANTES (rango real, toques TOTALES):")
        print(f"  {'='*50}")
        
        print(f"  📈 RESISTENCIAS (por encima):")
        if top_2_resistencias:
            for r in top_2_resistencias:
                recorrido = ((r["minimo"] - precio_actual) / precio_actual) * 100
                print(f"     💪 {r['rango']}€ - {r['toques']} toques (recorrido: {recorrido:.2f}%)")
        else:
            print(f"     ❌ No hay resistencias con suficientes toques")
        
        print(f"\n  📉 SOPORTES (por debajo):")
        if top_2_soportes:
            for s in top_2_soportes:
                distancia = ((precio_actual - s["maximo"]) / precio_actual) * 100
                print(f"     💪 {s['rango']}€ - {s['toques']} toques (distancia: {distancia:.2f}%)")
        else:
            print(f"     ❌ No hay soportes con suficientes toques")
        
        # ============================================
        # CONDICIÓN DE COMPRA
        # ============================================
        if smi_rapido is not None and smi_rapido < -40:
            print(f"  ✅ Condición 1: SMI en sobreventa")
            
            if giro_positivo:
                print(f"  ✅ Condición 2: Giro positivo")
                
                resistencia_valida = None
                for r in resistencias:
                    recorrido = ((r["minimo"] - precio_actual) / precio_actual) * 100
                    if recorrido >= 3:
                        resistencia_valida = r["minimo"]
                        print(f"  📊 Resistencia válida: {r['rango']}€ (recorrido: {recorrido:.2f}%)")
                        break
                
                if resistencia_valida:
                    print(f"  ✅ Condición 3: Resistencia válida encontrada")
                    
                    if smi_horario is not None and smi_horario < -40:
                        recomendacion = "COMPRA PERFECTA"
                        print(f"  🟢🟢 ¡COMPRA PERFECTA!")
                        guardar_recomendacion(ticker, nombre, precio_actual, 
                                              smi_horario, smi_rapido, smi_semanal,
                                              recomendacion, resistencia_valida)
                        contador_compras_perfectas += 1
                        contador_compras += 1
                    else:
                        recomendacion = "COMPRA (esperar momento)"
                        print(f"  🟢 ¡COMPRA!")
                        guardar_recomendacion(ticker, nombre, precio_actual, 
                                              smi_horario, smi_rapido, smi_semanal,
                                              recomendacion, resistencia_valida)
                        contador_compras += 1
                else:
                    print(f"  ❌ Condición 3: No hay resistencia válida (recorrido < 3%)")
                    guardar_recomendacion(ticker, nombre, precio_actual, 
                                          smi_horario, smi_rapido, smi_semanal,
                                          "SIN COMPRA (sin resistencia válida)", None)
            else:
                print(f"  ❌ Condición 2: SMI sin giro positivo")
                guardar_recomendacion(ticker, nombre, precio_actual, 
                                      smi_horario, smi_rapido, smi_semanal,
                                      "SIN COMPRA (SMI sin giro)", None)
        else:
            print(f"  ❌ Condición 1: SMI NO en sobreventa")
            guardar_recomendacion(ticker, nombre, precio_actual, 
                                  smi_horario, smi_rapido, smi_semanal,
                                  "SIN COMPRA", None)
        
        time.sleep(0.5)
    
    print("\n" + "=" * 70)
    print(f"✅ Análisis completado")
    print(f"📈 COMPRAS: {contador_compras} (Perfectas: {contador_compras_perfectas})")
    print("=" * 70)

if __name__ == "__main__":
    analizar_todo()
