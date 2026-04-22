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
    print("Asegúrate de configurarlas en GitHub Secrets")
    exit(1)
    
# Conectar a Supabase
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
    
    # Evitar división por cero
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
        print(f"  Error con {ticker} ({intervalo}): {e}")
        return None

def calcular_niveles_importantes(ticker, precio_actual):
    """
    Calcula soportes y resistencias IMPORTANTES basados en:
    - Múltiples toques del mismo precio
    - Volumen negociado en esos niveles
    """
    try:
        # Usar 1 año de datos diarios
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y", interval="1d")
        
        if hist.empty or len(hist) < 30:
            print(f"    ⚠️ Datos insuficientes, usando método simple")
            if len(hist) > 0:
                ultimos_30 = hist.tail(min(30, len(hist)))
                soporte_simple = round(ultimos_30['Low'].min(), 3)
                resistencia_simple = round(ultimos_30['High'].max(), 3)
            else:
                soporte_simple = round(precio_actual * 0.95, 3)
                resistencia_simple = round(precio_actual * 1.05, 3)
            
            return {
                "soportes": [{"precio": soporte_simple, "fuerza": 50}],
                "resistencias": [{"precio": resistencia_simple, "fuerza": 50}],
                "soporte_fuerte": soporte_simple,
                "resistencia_fuerte": resistencia_simple
            }
        
        # Diccionario para almacenar niveles
        niveles = {}
        
        # Recorrer cada vela
        for idx, row in hist.iterrows():
            alto = round(row['High'], 3)
            bajo = round(row['Low'], 3)
            cierre = round(row['Close'], 3)
            volumen = row['Volume']
            
            precios_a_considerar = [alto, bajo, cierre]
            
            for precio in precios_a_considerar:
                if precio not in niveles:
                    niveles[precio] = {
                        "toques": 0,
                        "volumen_total": 0,
                        "ultima_fecha": idx
                    }
                
                niveles[precio]["toques"] += 1
                niveles[precio]["volumen_total"] += volumen
                if idx > niveles[precio]["ultima_fecha"]:
                    niveles[precio]["ultima_fecha"] = idx
        
        # Calcular fuerza de cada nivel
        niveles_con_fuerza = []
        hoy = datetime.now()
        
        for precio, datos in niveles.items():
            toques = datos["toques"]
            volumen_promedio = datos["volumen_total"] / toques
            
            # Calcular antigüedad (convertir a timezone-aware)
            ultima_fecha = datos["ultima_fecha"]
            if ultima_fecha.tzinfo is None:
                # Si no tiene zona horaria, asumir UTC
                ultima_fecha = ultima_fecha.replace(tzinfo=timezone.utc)
            
            dias_diferencia = (hoy - ultima_fecha).days
            factor_actualidad = max(0, 1 - (dias_diferencia / 365))
            
            # Puntuación de fuerza (0 a 100)
            puntuacion_toques = min(40, toques * 5)
            puntuacion_volumen = min(30, volumen_promedio / 10000000 * 30)
            puntuacion_actualidad = factor_actualidad * 30
            
            fuerza = round(puntuacion_toques + puntuacion_volumen + puntuacion_actualidad, 1)
            
            niveles_con_fuerza.append({
                "precio": precio,
                "fuerza": fuerza,
                "toques": toques
            })
        
        # Separar soportes y resistencias
        soportes = [n for n in niveles_con_fuerza if n["precio"] < precio_actual]
        resistencias = [n for n in niveles_con_fuerza if n["precio"] > precio_actual]
        
        # Ordenar
        soportes.sort(key=lambda x: x["precio"], reverse=True)
        resistencias.sort(key=lambda x: x["precio"])
        
        # Tomar los 5 más cercanos
        soportes_cercanos = soportes[:5]
        resistencias_cercanas = resistencias[:5]
        
        # Identificar el más fuerte
        soporte_fuerte = max(soportes_cercanos, key=lambda x: x["fuerza"]) if soportes_cercanos else None
        resistencia_fuerte = max(resistencias_cercanas, key=lambda x: x["fuerza"]) if resistencias_cercanas else None
        
        if not soporte_fuerte:
            soporte_fuerte = {"precio": round(precio_actual * 0.95, 3), "fuerza": 50}
        if not resistencia_fuerte:
            resistencia_fuerte = {"precio": round(precio_actual * 1.05, 3), "fuerza": 50}
        
        return {
            "soportes": soportes_cercanos,
            "resistencias": resistencias_cercanas,
            "soporte_fuerte": soporte_fuerte["precio"],
            "resistencia_fuerte": resistencia_fuerte["precio"],
            "fuerza_soporte": soporte_fuerte["fuerza"],
            "fuerza_resistencia": resistencia_fuerte["fuerza"]
        }
    
    except Exception as e:
        print(f"    ⚠️ Error calculando niveles para {ticker}: {e}")
        return None

def calcular_precio_objetivo(ticker, precio_actual, smi_diario):
    """Calcula precio objetivo basado en soportes/resistencias"""
    
    niveles = calcular_niveles_importantes(ticker, precio_actual)
    
    if not niveles:
        return round(precio_actual * 1.05, 3)
    
    # Determinar dirección según el SMI diario
    if smi_diario is not None and smi_diario < -40:
        precio_objetivo = niveles["resistencia_fuerte"]
        print(f"    🎯 Objetivo: RESISTENCIA {precio_objetivo}€")
    elif smi_diario is not None and smi_diario > 40:
        precio_objetivo = niveles["soporte_fuerte"]
        print(f"    🎯 Objetivo: SOPORTE {precio_objetivo}€")
    else:
        # Usar el nivel más cercano
        distancia_soporte = precio_actual - niveles["soporte_fuerte"]
        distancia_resistencia = niveles["resistencia_fuerte"] - precio_actual
        
        if distancia_resistencia < distancia_soporte:
            precio_objetivo = niveles["resistencia_fuerte"]
        else:
            precio_objetivo = niveles["soporte_fuerte"]
    
    return round(precio_objetivo, 3)

def guardar_recomendacion(ticker, nombre, precio, smi_h, smi_d, smi_s, recomendacion, precio_obj):
    """Guarda TODAS las empresas en Supabase"""
    try:
        # Usar UTC para evitar problemas de zona horaria
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
        print(f"  ❌ Error guardando {nombre}: {e}")

def analizar_todo():
    """Analiza todas las empresas y guarda TODAS en Supabase"""
    print(f"🚀 Iniciando análisis - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)
    print("📊 LÓGICA: El DIARIO marca si hay COMPRA")
    print("📊 PRECIO OBJETIVO: Basado en SOPORTES/RESISTENCIAS")
    print("📊 SE GUARDAN TODAS LAS EMPRESAS")
    print("=" * 60)
    
    contador_compras = 0
    contador_compras_perfectas = 0
    contador_sin_compra = 0
    
    for ticker, nombre in EMPRESAS:
        print(f"\n📊 Analizando: {nombre} ({ticker})")
        
        # Obtener precio actual
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            precio_actual = info.get("currentPrice", info.get("regularMarketPrice"))
            if precio_actual is None:
                print(f"  ⚠️ No se pudo obtener precio")
                guardar_recomendacion(ticker, nombre, None, None, None, None, "SIN DATOS", None)
                continue
        except Exception as e:
            print(f"  ⚠️ Error obteniendo precio: {e}")
            guardar_recomendacion(ticker, nombre, None, None, None, None, "ERROR", None)
            continue
        
        # Obtener SMI
        smi_horario = obtener_smi_timeframe(ticker, "1h", "7d")
        smi_diario = obtener_smi_timeframe(ticker, "1d", "90d")
        smi_semanal = obtener_smi_timeframe(ticker, "1wk", "1y")
        
        print(f"  💰 Precio: {precio_actual}€")
        print(f"  📊 SMI DIARIO: {smi_diario}")
        print(f"  📊 SMI HORARIO: {smi_horario}")
        print(f"  📊 SMI Semanal: {smi_semanal}")
        
        # LÓGICA DE COMPRA
        if smi_diario is not None and smi_diario < -40:
            
            print(f"  🔍 Calculando precio objetivo...")
            precio_objetivo = calcular_precio_objetivo(ticker, precio_actual, smi_diario)
            
            if smi_horario is not None and smi_horario < -40:
                recomendacion = "COMPRA PERFECTA"
                print(f"  🟢🟢 ¡COMPRA PERFECTA!")
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
            contador_sin_compra += 1
        
        time.sleep(0.5)
    
    print("\n" + "=" * 60)
    print(f"✅ Análisis completado")
    print(f"📈 Total empresas: {len(EMPRESAS)}")
    print(f"🟢 COMPRAS: {contador_compras}")
    print(f"🎯 COMPRAS PERFECTAS: {contador_compras_perfectas}")
    print(f"⚪ SIN COMPRA: {contador_sin_compra}")
    print("=" * 60)

if __name__ == "__main__":
    analizar_todo()
