import yfinance as yf
import pandas as pd
import numpy as np
from supabase import create_client, Client
from datetime import datetime
import time
import os

# ============================================
# CONFIGURACIÓN DE SUPABASE (CAMBIAR AQUÍ)
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
    """
    Obtiene el SMI para un timeframe específico
    intervalo: '1h', '1d', '1wk'
    periodo: '30d', '90d', '1y'
    """
    try:
        stock = yf.Ticker(ticker)
        datos = stock.history(period=periodo, interval=intervalo)
        
        if datos.empty:
            return None
        
        smi = calcular_smi(datos['High'], datos['Low'], datos['Close'])
        smi_ultimo = smi.dropna().iloc[-1] if not smi.dropna().empty else None
        
        return round(smi_ultimo, 2) if smi_ultimo is not None else None
    
    except Exception as e:
        print(f"Error con {ticker} ({intervalo}): {e}")
        return None

def guardar_recomendacion(ticker, nombre, precio, smi_h, smi_d, smi_s, recomendacion, precio_obj):
    """Guarda una recomendación en Supabase"""
    try:
        data = {
            "fecha": datetime.now().isoformat(),
            "ticker": ticker,
            "nombre_empresa": nombre,
            "precio_cierre": precio,
            "smi_horario": smi_h,
            "smi_diario": smi_d,
            "smi_semanal": smi_s,
            "recomendacion": recomendacion,
            "precio_objetivo": precio_obj
        }
        
        supabase.table("recomendaciones").insert(data).execute()
        print(f"✅ Guardado: {nombre} - {recomendacion}")
        
    except Exception as e:
        print(f"❌ Error guardando {nombre}: {e}")

def analizar_todo():
    """Analiza todas las empresas del IBEX35 con lógica multitemporal"""
    print(f"🚀 Iniciando análisis - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    print("📊 LÓGICA: El DIARIO marca si hay COMPRA, el HORARIO el momento exacto")
    print("=" * 50)
    
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
                print(f"  ⚠️ No se pudo obtener precio, saltando...")
                continue
        except Exception as e:
            print(f"  ⚠️ Error obteniendo precio: {e}")
            continue
        
        # Obtener SMI en los 3 timeframes
        smi_horario = obtener_smi_timeframe(ticker, "1h", "7d")
        smi_diario = obtener_smi_timeframe(ticker, "1d", "90d")
        smi_semanal = obtener_smi_timeframe(ticker, "1wk", "1y")
        
        print(f"  💰 Precio: {precio_actual}€")
        print(f"  📊 SMI DIARIO (tendencia): {smi_diario}")
        print(f"  📊 SMI HORARIO (momento): {smi_horario}")
        print(f"  📊 SMI Semanal (contexto): {smi_semanal}")
        
        # ============================================
        # LÓGICA CORRECTA: El DIARIO manda
        # ============================================
        
        # PRIMERO: ¿El DIARIO da señal de compra?
        if smi_diario is not None and smi_diario < -40:
            
            # SEGUNDO: ¿El HORARIO también da señal?
            if smi_horario is not None and smi_horario < -40:
                # ¡COMPRA PERFECTA! Ambos timeframes coinciden
                recomendacion = "COMPRA PERFECTA"
                precio_objetivo = round(precio_actual * 1.05, 3)
                print(f"  🟢🟢 ¡COMPRA PERFECTA! Diario={smi_diario}, Horario={smi_horario}")
                guardar_recomendacion(ticker, nombre, precio_actual, 
                                      smi_horario, smi_diario, smi_semanal,
                                      recomendacion, precio_objetivo)
                contador_compras_perfectas += 1
                contador_compras += 1
                
            else:
                # COMPRA NORMAL: El diario da señal pero el horario aún no
                recomendacion = "COMPRA (esperar momento)"
                precio_objetivo = round(precio_actual * 1.05, 3)
                print(f"  🟢 COMPRA (momento no perfecto). Diario={smi_diario}, Horario={smi_horario}")
                guardar_recomendacion(ticker, nombre, precio_actual, 
                                      smi_horario, smi_diario, smi_semanal,
                                      recomendacion, precio_objetivo)
                contador_compras += 1
        else:
            print(f"  ⚪ Sin señal de compra (SMI Diario: {smi_diario} - necesita < -40)")
        
        # Esperar para no saturar Yahoo Finance
        time.sleep(0.5)
    
    print("\n" + "=" * 50)
    print(f"✅ Análisis completado")
    print(f"📈 Total señales de COMPRA: {contador_compras}")
    print(f"🎯 De ellas, COMPRAS PERFECTAS (momento exacto): {contador_compras_perfectas}")
    
    if contador_compras == 0:
        print("📭 No hay señales de compra en este momento. Vuelve a consultar más tarde.")

if __name__ == "__main__":
    analizar_todo()
