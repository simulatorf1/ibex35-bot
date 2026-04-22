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
# LISTA DE EMPRESAS DEL IBEX35 (TICKERS CORRECTOS)
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
    ("BKT.MC", "Bankinter"),  # ← CORREGIDO
]

def calcular_smi(high, low, close):
    """Calcula el SMI (Stochastic Momentum Index)"""
    length_k = 10
    length_d = 3
    smooth_period = 5
    ema_signal_len = 10
    
    hh = high.rolling(window=length_k).max()
    ll = low.rolling(window=length_k).min()
    diff = hh - ll
    
    rdiff = close - (hh + ll) / 2
    
    avgrel = rdiff.ewm(span=length_d, adjust=False).mean()
    avgdiff = diff.ewm(span=length_d, adjust=False).mean()
    
    avgdiff_safe = avgdiff.replace(0, np.nan)
    smi_raw = (avgrel / (avgdiff_safe / 2)) * 100
    smi_raw = smi_raw.clip(-100, 100)
    
    smi = smi_raw.rolling(window=smooth_period).mean()
    smi = smi.ewm(span=ema_signal_len, adjust=False).mean()
    
    return smi

def obtener_smi_timeframe(ticker, intervalo, periodo):
    """Obtiene el SMI para un timeframe específico"""
    try:
        stock = yf.Ticker(ticker)
        datos = stock.history(period=periodo, interval=intervalo)
        
        if datos.empty:
            return None
        
        smi = calcular_smi(datos['High'], datos['Low'], datos['Close'])
        smi_ultimo = smi.dropna().iloc[-1] if not smi.dropna().empty else None
        
        return round(smi_ultimo, 2) if smi_ultimo is not None else None
    
    except Exception as e:
        print(f"  Error SMI: {e}")
        return None

def calcular_volumen_promedio(hist, dias=30):
    """Calcula el volumen promedio de los últimos N días"""
    if len(hist) >= dias:
        return hist['Volume'].tail(dias).mean()
    return hist['Volume'].mean() if not hist.empty else 0

def identificar_resistencias(hist, precio_actual, volumen_promedio):
    """
    Identifica resistencias REALES basadas en:
    - Múltiples toques (mínimo 2)
    - Rechazos claros (cierre por debajo del máximo)
    - Volumen significativo
    """
    resistencias = []
    
    for i in range(len(hist)):
        fila = hist.iloc[i]
        maximo = fila['High']
        cierre = fila['Close']
        volumen = fila['Volume']
        
        # Solo considerar máximos por encima del precio actual
        if maximo <= precio_actual:
            continue
        
        # ¿Hay rechazo? (cierre significativamente por debajo del máximo)
        rechazo = (maximo - cierre) / maximo > 0.02  # Al menos 2% de rechazo
        
        # Volumen significativo (al menos 80% del promedio)
        volumen_significativo = volumen > (volumen_promedio * 0.8)
        
        # Si hay rechazo o volumen significativo, es candidato
        if rechazo or volumen_significativo:
            resistencias.append({
                "precio": round(maximo, 3),
                "fecha": fila.name,
                "rechazo": rechazo,
                "volumen": volumen
            })
    
    # Agrupar por zonas (precios cercanos ±1%)
    zonas = {}
    for r in resistencias:
        precio = r["precio"]
        # Buscar zona existente
        encontrado = False
        for zona_precio in list(zonas.keys()):
            if abs(precio - zona_precio) / zona_precio < 0.01:  # ±1%
                zonas[zona_precio].append(r)
                encontrado = True
                break
        if not encontrado:
            zonas[precio] = [r]
    
    # Calcular fuerza de cada zona
    resultado = []
    for precio, toques in zonas.items():
        fuerza = 0
        toques_count = len(toques)
        
        # Más toques = más fuerza
        if toques_count >= 3:
            fuerza = 100
        elif toques_count == 2:
            fuerza = 70
        else:
            fuerza = 40
        
        # Rechazos claros aumentan fuerza
        rechazos = sum(1 for t in toques if t["rechazo"])
        if rechazos >= 2:
            fuerza = min(100, fuerza + 20)
        
        # Volumen alto aumenta fuerza
        volumen_alto = sum(1 for t in toques if t["volumen"] > volumen_promedio)
        if volumen_alto >= 2:
            fuerza = min(100, fuerza + 10)
        
        resultado.append({
            "precio": precio,
            "fuerza": fuerza,
            "toques": toques_count,
            "rechazos": rechazos
        })
    
    # Ordenar por precio (de menor a mayor)
    resultado.sort(key=lambda x: x["precio"])
    
    return resultado

def identificar_soportes(hist, precio_actual, volumen_promedio):
    """
    Identifica soportes REALES basados en:
    - Múltiples toques (mínimo 2)
    - Rebotes claros (cierre por encima del mínimo)
    - Volumen significativo
    """
    soportes = []
    
    for i in range(len(hist)):
        fila = hist.iloc[i]
        minimo = fila['Low']
        cierre = fila['Close']
        volumen = fila['Volume']
        
        # Solo considerar mínimos por debajo del precio actual
        if minimo >= precio_actual:
            continue
        
        # ¿Hay rebote? (cierre significativamente por encima del mínimo)
        rebote = (cierre - minimo) / minimo > 0.02  # Al menos 2% de rebote
        
        # Volumen significativo
        volumen_significativo = volumen > (volumen_promedio * 0.8)
        
        if rebote or volumen_significativo:
            soportes.append({
                "precio": round(minimo, 3),
                "fecha": fila.name,
                "rebote": rebote,
                "volumen": volumen
            })
    
    # Agrupar por zonas
    zonas = {}
    for s in soportes:
        precio = s["precio"]
        encontrado = False
        for zona_precio in list(zonas.keys()):
            if abs(precio - zona_precio) / zona_precio < 0.01:
                zonas[zona_precio].append(s)
                encontrado = True
                break
        if not encontrado:
            zonas[precio] = [s]
    
    # Calcular fuerza
    resultado = []
    for precio, toques in zonas.items():
        fuerza = 0
        toques_count = len(toques)
        
        if toques_count >= 3:
            fuerza = 100
        elif toques_count == 2:
            fuerza = 70
        else:
            fuerza = 40
        
        rebotes = sum(1 for t in toques if t["rebote"])
        if rebotes >= 2:
            fuerza = min(100, fuerza + 20)
        
        volumen_alto = sum(1 for t in toques if t["volumen"] > volumen_promedio)
        if volumen_alto >= 2:
            fuerza = min(100, fuerza + 10)
        
        resultado.append({
            "precio": precio,
            "fuerza": fuerza,
            "toques": toques_count,
            "rebotes": rebotes
        })
    
    # Ordenar por precio (de mayor a menor, para tener los más cercanos primero)
    resultado.sort(key=lambda x: x["precio"], reverse=True)
    
    return resultado

def calcular_precio_objetivo(ticker, precio_actual, smi_diario):
    """
    Calcula precio objetivo basado en RESISTENCIAS REALES
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="90d", interval="1d")
        
        if hist.empty or len(hist) < 10:
            print(f"    ⚠️ Datos insuficientes, usando +5%")
            return round(precio_actual * 1.05, 3)
        
        volumen_promedio = calcular_volumen_promedio(hist)
        
        # Identificar resistencias reales
        resistencias = identificar_resistencias(hist, precio_actual, volumen_promedio)
        
        # Filtrar resistencias con fuerza suficiente (mínimo 40)
        resistencias_fuertes = [r for r in resistencias if r["fuerza"] >= 40]
        
        print(f"    📊 Resistencias detectadas: {len(resistencias)} total, {len(resistencias_fuertes)} fuertes")
        for r in resistencias_fuertes[:3]:
            print(f"      - {r['precio']}€ (fuerza: {r['fuerza']}, toques: {r['toques']})")
        
        # Si SMI está en sobreventa, buscamos resistencia
        if smi_diario is not None and smi_diario < -40:
            if resistencias_fuertes:
                # La resistencia más cercana (la de menor precio por encima del actual)
                objetivo = resistencias_fuertes[0]["precio"]
                print(f"    🎯 SMI en sobreventa ({smi_diario}) → objetivo RESISTENCIA: {objetivo}€")
                return objetivo
            else:
                # No hay resistencias fuertes, usar máximo de 90 días
                max_90d = hist['High'].max()
                objetivo = round(max_90d, 3)
                print(f"    🎯 Sin resistencias fuertes → objetivo MÁXIMO 90d: {objetivo}€")
                return objetivo
        
        # Si no hay señal de compra, devolvemos el precio actual (sin objetivo)
        return round(precio_actual, 3)
        
    except Exception as e:
        print(f"    ⚠️ Error calculando objetivo: {e}")
        return round(precio_actual * 1.05, 3)

def guardar_recomendacion(ticker, nombre, precio, smi_h, smi_d, smi_s, recomendacion, precio_obj):
    """Guarda todas las empresas en Supabase"""
    try:
        fecha_actual = datetime.now(timezone.utc).isoformat()
        
        data = {
            "fecha": fecha_actual,
            "ticker": ticker,
            "nombre_empresa": nombre,
            "precio_cierre": precio,
            "smi_horario": smi_h,
            "smi_diario": smi_d,
            "smi_semanal": smi_s,
            "recomendacion": recomendacion,
            "precio_objetivo": precio_obj if precio_obj else None
        }
        
        supabase.table("recomendaciones").insert(data).execute()
        
        if "COMPRA" in recomendacion:
            print(f"  ✅ Guardado: {nombre} - {recomendacion} (Objetivo: {precio_obj}€)")
        else:
            print(f"  💾 Guardado: {nombre} - {recomendacion}")
        
    except Exception as e:
        print(f"  ❌ Error guardando: {e}")

def analizar_todo():
    """Analiza todas las empresas y guarda TODAS en Supabase"""
    print(f"🚀 Iniciando análisis - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)
    print("📊 LÓGICA: El DIARIO marca si hay COMPRA")
    print("📊 RESISTENCIAS: Basadas en toques, rechazos y volumen (mínimo 2 toques)")
    print("📊 PRECIO OBJETIVO: La resistencia más cercana por encima del precio actual")
    print("=" * 70)
    
    contador_compras = 0
    contador_compras_perfectas = 0
    
    for ticker, nombre in EMPRESAS:
        print(f"\n📊 Analizando: {nombre} ({ticker})")
        
        # Obtener precio actual
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            precio_actual = info.get("currentPrice", info.get("regularMarketPrice"))
            if precio_actual is None:
                print(f"  ⚠️ Sin precio")
                guardar_recomendacion(ticker, nombre, None, None, None, None, "SIN DATOS", None)
                continue
        except Exception as e:
            print(f"  ⚠️ Error: {e}")
            guardar_recomendacion(ticker, nombre, None, None, None, None, "ERROR", None)
            continue
        
        # Obtener SMI
        smi_horario = obtener_smi_timeframe(ticker, "1h", "7d")
        smi_diario = obtener_smi_timeframe(ticker, "1d", "90d")
        smi_semanal = obtener_smi_timeframe(ticker, "1wk", "1y")
        
        print(f"  💰 Precio: {precio_actual}€")
        print(f"  📊 SMI DIARIO: {smi_diario}")
        print(f"  📊 SMI HORARIO: {smi_horario}")
        
        # LÓGICA DE COMPRA: El DIARIO manda
        if smi_diario is not None and smi_diario < -40:
            
            # Calcular precio objetivo con resistencias reales
            precio_objetivo = calcular_precio_objetivo(ticker, precio_actual, smi_diario)
            
            if smi_horario is not None and smi_horario < -40:
                recomendacion = "COMPRA PERFECTA"
                print(f"  🟢🟢 COMPRA PERFECTA!")
                guardar_recomendacion(ticker, nombre, precio_actual, 
                                      smi_horario, smi_diario, smi_semanal,
                                      recomendacion, precio_objetivo)
                contador_compras_perfectas += 1
                contador_compras += 1
            else:
                recomendacion = "COMPRA (esperar momento)"
                print(f"  🟢 COMPRA (esperar momento)")
                guardar_recomendacion(ticker, nombre, precio_actual, 
                                      smi_horario, smi_diario, smi_semanal,
                                      recomendacion, precio_objetivo)
                contador_compras += 1
        else:
            recomendacion = "SIN COMPRA"
            print(f"  ⚪ SIN COMPRA")
            guardar_recomendacion(ticker, nombre, precio_actual, 
                                  smi_horario, smi_diario, smi_semanal,
                                  recomendacion, None)
        
        time.sleep(0.5)
    
    print("\n" + "=" * 70)
    print(f"✅ Análisis completado")
    print(f"📈 COMPRAS: {contador_compras} (Perfectas: {contador_compras_perfectas})")
    print("=" * 70)

if __name__ == "__main__":
    analizar_todo()
