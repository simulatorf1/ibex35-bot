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
    ("BKIA.MC", "Bankinter"),
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

def calcular_soportes_resistencias(ticker, precio_actual):
    """
    Calcula soportes y resistencias de forma SIMPLE y ROBUSTA
    Usa máximos y mínimos de los últimos 90 días
    """
    try:
        stock = yf.Ticker(ticker)
        # Usar 90 días de datos diarios
        hist = stock.history(period="90d", interval="1d")
        
        if hist.empty or len(hist) < 10:
            print(f"    ⚠️ Datos insuficientes, usando método simple")
            return {
                "soporte_cercano": round(precio_actual * 0.97, 3),
                "resistencia_cercana": round(precio_actual * 1.03, 3),
                "soporte_fuerte": round(precio_actual * 0.95, 3),
                "resistencia_fuerte": round(precio_actual * 1.05, 3)
            }
        
        # Obtener máximos y mínimos del período
        max_90d = hist['High'].max()
        min_90d = hist['Low'].min()
        
        # Obtener máximos y mínimos de los últimos 30 días (más relevantes)
        ultimos_30 = hist.tail(30)
        max_30d = ultimos_30['High'].max()
        min_30d = ultimos_30['Low'].min()
        
        # Obtener cierres anteriores como posibles soportes/resistencias
        cierres = hist['Close'].tail(20).tolist()
        
        # Buscar resistencias cercanas (precios por encima del actual)
        resistencias = []
        for precio in cierres:
            if precio > precio_actual and precio not in resistencias:
                resistencias.append(round(precio, 3))
        
        # Buscar soportes cercanos (precios por debajo del actual)
        soportes = []
        for precio in cierres:
            if precio < precio_actual and precio not in soportes:
                soportes.append(round(precio, 3))
        
        # Ordenar
        resistencias.sort()
        soportes.sort(reverse=True)
        
        # Resistencia más cercana
        resistencia_cercana = resistencias[0] if resistencias else round(max_30d, 3)
        
        # Soporte más cercano
        soporte_cercano = soportes[0] if soportes else round(min_30d, 3)
        
        # Si la resistencia calculada es muy cercana (<0.5%), usar +3%
        if resistencia_cercana - precio_actual < 0.05:
            resistencia_cercana = round(precio_actual * 1.03, 3)
        
        # Si el soporte calculado es muy cercano (<0.5%), usar -3%
        if precio_actual - soporte_cercano < 0.05:
            soporte_cercano = round(precio_actual * 0.97, 3)
        
        print(f"    📉 Soporte cercano: {soporte_cercano}€")
        print(f"    📈 Resistencia cercana: {resistencia_cercana}€")
        print(f"    📊 Máximo 30 días: {round(max_30d, 3)}€")
        print(f"    📊 Mínimo 30 días: {round(min_30d, 3)}€")
        
        return {
            "soporte_cercano": soporte_cercano,
            "resistencia_cercana": resistencia_cercana,
            "soporte_fuerte": round(min_30d, 3),
            "resistencia_fuerte": round(max_30d, 3),
            "max_30d": round(max_30d, 3),
            "min_30d": round(min_30d, 3)
        }
    
    except Exception as e:
        print(f"    ⚠️ Error: {e}")
        return {
            "soporte_cercano": round(precio_actual * 0.97, 3),
            "resistencia_cercana": round(precio_actual * 1.03, 3),
            "soporte_fuerte": round(precio_actual * 0.95, 3),
            "resistencia_fuerte": round(precio_actual * 1.05, 3)
        }

def calcular_precio_objetivo(ticker, precio_actual, smi_diario):
    """
    Calcula precio objetivo basado en SOPORTES y RESISTENCIAS reales
    """
    niveles = calcular_soportes_resistencias(ticker, precio_actual)
    
    if not niveles:
        return round(precio_actual * 1.05, 3)
    
    # Si el SMI diario está en sobreventa (< -40) → se espera subida
    if smi_diario is not None and smi_diario < -40:
        # Objetivo = resistencia cercana
        precio_objetivo = niveles["resistencia_cercana"]
        print(f"    🎯 SMI en sobreventa ({smi_diario}) → objetivo RESISTENCIA: {precio_objetivo}€")
    else:
        # Objetivo = soporte cercano (por defecto)
        precio_objetivo = niveles["soporte_cercano"]
        print(f"    🎯 Objetivo SOPORTE: {precio_objetivo}€")
    
    return round(precio_objetivo, 3)

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
    print("=" * 60)
    print("📊 LÓGICA: El DIARIO marca si hay COMPRA")
    print("📊 PRECIO OBJETIVO: Basado en SOPORTES/RESISTENCIAS reales")
    print("=" * 60)
    
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
            
            # Calcular precio objetivo con soportes/resistencias reales
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
    
    print("\n" + "=" * 60)
    print(f"✅ Análisis completado")
    print(f"📈 COMPRAS: {contador_compras} (Perfectas: {contador_compras_perfectas})")
    print("=" * 60)

if __name__ == "__main__":
    analizar_todo()
