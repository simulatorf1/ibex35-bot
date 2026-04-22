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
    """Analiza todas las empresas del IBEX35"""
    print(f"🚀 Iniciando análisis - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
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
        except:
            print(f"  ⚠️ Error obteniendo precio, saltando...")
            continue
        
        # Obtener SMI en los 3 timeframes
        smi_horario = obtener_smi_timeframe(ticker, "1h", "7d")      # Horario (últimos 7 días)
        smi_diario = obtener_smi_timeframe(ticker, "1d", "90d")      # Diario (últimos 90 días)
        smi_semanal = obtener_smi_timeframe(ticker, "1wk", "1y")     # Semanal (último año)
        
        print(f"  💰 Precio: {precio_actual}€")
        print(f"  📊 SMI Horario: {smi_horario}")
        print(f"  📊 SMI Diario: {smi_diario}")
        print(f"  📊 SMI Semanal: {smi_semanal}")
        
        # LÓGICA DE COMPRA: SMI horario < -40 (sobreventa)
        if smi_horario is not None and smi_horario < -40:
            recomendacion = "COMPRA"
            precio_objetivo = round(precio_actual * 1.05, 3)  # Objetivo +5%
            print(f"  🟢 ¡SEÑAL DE COMPRA! SMI horario en {smi_horario}")
            guardar_recomendacion(ticker, nombre, precio_actual, 
                                  smi_horario, smi_diario, smi_semanal,
                                  recomendacion, precio_objetivo)
        else:
            print(f"  ⚪ Sin señal de compra (SMI horario: {smi_horario})")
        
        # Esperar 1 segundo entre empresas para no saturar Yahoo Finance
        time.sleep(1)
    
    print("\n" + "=" * 50)
    print("✅ Análisis completado")

if __name__ == "__main__":
    analizar_todo()
