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

def calcular_smi_completo(high, low, close):
    """Calcula el SMI completo: rápido y lento"""
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
    
    # RÁPIDO
    smi_rapido = smi_raw.rolling(window=smooth_period).mean()
    # LENTO
    smi_lento = smi_rapido.ewm(span=ema_signal_len, adjust=False).mean()
    
    return smi_rapido, smi_lento

def obtener_smis_diario(ticker):
    """Obtiene las dos líneas del SMI diario"""
    try:
        stock = yf.Ticker(ticker)
        datos = stock.history(period="90d", interval="1d")
        
        if datos.empty:
            return None, None, None, False
        
        smi_rapido, smi_lento = calcular_smi_completo(datos['High'], datos['Low'], datos['Close'])
        
        smi_rapido_clean = smi_rapido.dropna()
        smi_lento_clean = smi_lento.dropna()
        
        if len(smi_rapido_clean) < 2 or len(smi_lento_clean) < 1:
            return None, None, None, False
        
        ultimo_rapido = round(smi_rapido_clean.iloc[-1], 2)
        ultimo_lento = round(smi_lento_clean.iloc[-1], 2)
        
        # Calcular pendiente del RÁPIDO
        penultimo_rapido = smi_rapido_clean.iloc[-2]
        pendiente = round(ultimo_rapido - penultimo_rapido, 2)
        giro_positivo = pendiente > 0
        
        return ultimo_rapido, ultimo_lento, pendiente, giro_positivo
    
    except Exception as e:
        print(f"  Error SMI: {e}")
        return None, None, None, False

def obtener_smi_timeframe_simple(ticker, intervalo, periodo):
    """Obtiene solo la línea LENTA del SMI para otros timeframes"""
    try:
        stock = yf.Ticker(ticker)
        datos = stock.history(period=periodo, interval=intervalo)
        
        if datos.empty:
            return None
        
        _, smi_lento = calcular_smi_completo(datos['High'], datos['Low'], datos['Close'])
        smi_lento_clean = smi_lento.dropna()
        
        if smi_lento_clean.empty:
            return None
        
        return round(smi_lento_clean.iloc[-1], 2)
    
    except Exception as e:
        print(f"  Error SMI simple: {e}")
        return None

def calcular_soportes_y_resistencias(ticker, precio_actual):
    """
    Calcula SOPORTES y RESISTENCIAS reales para MOSTRAR siempre
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="90d", interval="1d")
        
        if hist.empty or len(hist) < 10:
            return None, None
        
        volumen_promedio = hist['Volume'].tail(30).mean()
        
        # Buscar resistencias (máximos por encima del precio actual)
        resistencias = []
        for i in range(len(hist)):
            fila = hist.iloc[i]
            maximo = fila['High']
            cierre = fila['Close']
            volumen = fila['Volume']
            
            if maximo <= precio_actual:
                continue
            
            rechazo = (maximo - cierre) / maximo > 0.02
            volumen_significativo = volumen > (volumen_promedio * 0.8)
            
            if rechazo or volumen_significativo:
                resistencias.append(round(maximo, 3))
        
        # Buscar soportes (mínimos por debajo del precio actual)
        soportes = []
        for i in range(len(hist)):
            fila = hist.iloc[i]
            minimo = fila['Low']
            cierre = fila['Close']
            volumen = fila['Volume']
            
            if minimo >= precio_actual:
                continue
            
            rebote = (cierre - minimo) / minimo > 0.02
            volumen_significativo = volumen > (volumen_promedio * 0.8)
            
            if rebote or volumen_significativo:
                soportes.append(round(minimo, 3))
        
        # Eliminar duplicados y ordenar
        resistencias = sorted(list(set(resistencias)))
        soportes = sorted(list(set(soportes)), reverse=True)
        
        # Resistencia más cercana (la más baja por encima)
        resistencia_cercana = resistencias[0] if resistencias else None
        
        # Soporte más cercano (el más alto por debajo)
        soporte_cercano = soportes[0] if soportes else None
        
        # Si no hay resistencias, usar máximo de 90 días
        if not resistencia_cercana:
            resistencia_cercana = round(hist['High'].max(), 3)
        
        # Si no hay soportes, usar mínimo de 90 días
        if not soporte_cercano:
            soporte_cercano = round(hist['Low'].min(), 3)
        
        return resistencia_cercana, soporte_cercano
    
    except Exception as e:
        print(f"  Error niveles: {e}")
        return None, None

def verificar_recorrido_suficiente(precio_actual, precio_objetivo):
    """Verifica al menos 3% de recorrido"""
    if precio_objetivo is None or precio_actual is None:
        return False, 0
    
    porcentaje = ((precio_objetivo - precio_actual) / precio_actual) * 100
    return porcentaje >= 3, round(porcentaje, 2)

def guardar_recomendacion(ticker, nombre, precio, smi_h, smi_rapido, smi_lento, smi_s, 
                          recomendacion, precio_obj, resistencia, soporte):
    """Guarda todas las empresas en Supabase"""
    try:
        fecha_actual = datetime.now(timezone.utc).isoformat()
        
        data = {
            "fecha": fecha_actual,
            "ticker": ticker,
            "nombre_empresa": nombre,
            "precio_cierre": precio,
            "smi_horario": smi_h,
            "smi_diario": smi_lento,
            "smi_diario_rapido": smi_rapido,
            "smi_semanal": smi_s,
            "recomendacion": recomendacion,
            "precio_objetivo": precio_obj if precio_obj else None
        }
        
        supabase.table("recomendaciones").insert(data).execute()
        
        print(f"  💾 Guardado: {nombre}")
        print(f"     📈 Soporte: {soporte}€ | Resistencia: {resistencia}€")
        
        if "COMPRA" in recomendacion:
            print(f"     🎯 Objetivo: {precio_obj}€ | Recorrido: {((precio_obj-precio)/precio)*100:.1f}%")
        
    except Exception as e:
        print(f"  ❌ Error guardando: {e}")

def analizar_todo():
    """Analiza todas las empresas mostrando SIEMPRE soportes y resistencias"""
    print(f"🚀 Iniciando análisis - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)
    print("📊 CONDICIONES PARA COMPRA:")
    print("   1. SMI LENTO < -40 (sobreventa)")
    print("   2. SMI RÁPIDO con GIRO POSITIVO")
    print("   3. Recorrido hasta resistencia > 3%")
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
                continue
        except Exception as e:
            print(f"  ⚠️ Error precio: {e}")
            continue
        
        # Obtener SMI Diario (rápido y lento)
        smi_rapido, smi_lento, pendiente, giro_positivo = obtener_smis_diario(ticker)
        
        # Obtener SMI Horario y Semanal
        smi_horario = obtener_smi_timeframe_simple(ticker, "1h", "7d")
        smi_semanal = obtener_smi_timeframe_simple(ticker, "1wk", "1y")
        
        # Calcular soporte y resistencia (SIEMPRE, haya o no compra)
        resistencia, soporte = calcular_soportes_y_resistencias(ticker, precio_actual)
        
        print(f"  💰 Precio: {precio_actual}€")
        print(f"  📊 SMI LENTO (sobreventa): {smi_lento}")
        print(f"  📊 SMI RÁPIDO (giro): {smi_rapido}")
        print(f"  📊 Pendiente RÁPIDO: {pendiente} (Giro: {'✅' if giro_positivo else '❌'})")
        print(f"  📊 SMI HORARIO: {smi_horario}")
        print(f"  📈 SOPORTE: {soporte}€")
        print(f"  📉 RESISTENCIA: {resistencia}€")
        
        # ============================================
        # CONDICIÓN 1: SMI LENTO en sobreventa (< -40)
        # ============================================
        if smi_lento is not None and smi_lento < -40:
            print(f"  ✅ Condición 1: SMI LENTO en sobreventa")
            
            # ============================================
            # CONDICIÓN 2: SMI RÁPIDO con giro positivo
            # ============================================
            if giro_positivo:
                print(f"  ✅ Condición 2: SMI RÁPIDO con giro positivo")
                
                # ============================================
                # CONDICIÓN 3: Verificar recorrido
                # ============================================
                if resistencia:
                    recorrido_valido, porcentaje = verificar_recorrido_suficiente(precio_actual, resistencia)
                    
                    if recorrido_valido:
                        print(f"  ✅ Condición 3: Recorrido suficiente ({porcentaje}% > 3%)")
                        
                        if smi_horario is not None and smi_horario < -40:
                            recomendacion = "COMPRA PERFECTA"
                            print(f"  🟢🟢 ¡COMPRA PERFECTA!")
                            guardar_recomendacion(ticker, nombre, precio_actual, 
                                                  smi_horario, smi_rapido, smi_lento, smi_semanal,
                                                  recomendacion, resistencia, resistencia, soporte)
                            contador_compras_perfectas += 1
                            contador_compras += 1
                        else:
                            recomendacion = "COMPRA (esperar momento)"
                            print(f"  🟢 ¡COMPRA!")
                            guardar_recomendacion(ticker, nombre, precio_actual, 
                                                  smi_horario, smi_rapido, smi_lento, smi_semanal,
                                                  recomendacion, resistencia, resistencia, soporte)
                            contador_compras += 1
                    else:
                        print(f"  ❌ Condición 3: Recorrido insuficiente ({porcentaje}% < 3%)")
                        guardar_recomendacion(ticker, nombre, precio_actual, 
                                              smi_horario, smi_rapido, smi_lento, smi_semanal,
                                              "SIN COMPRA (recorrido insuficiente)", 
                                              None, resistencia, soporte)
                else:
                    print(f"  ❌ No se pudo calcular resistencia")
                    guardar_recomendacion(ticker, nombre, precio_actual, 
                                          smi_horario, smi_rapido, smi_lento, smi_semanal,
                                          "SIN COMPRA (sin resistencia clara)", 
                                          None, resistencia, soporte)
            else:
                print(f"  ❌ Condición 2: SMI RÁPIDO sin giro positivo")
                guardar_recomendacion(ticker, nombre, precio_actual, 
                                      smi_horario, smi_rapido, smi_lento, smi_semanal,
                                      "SIN COMPRA (SMI sin giro)", 
                                      None, resistencia, soporte)
        else:
            print(f"  ❌ Condición 1: SMI LENTO NO en sobreventa ({smi_lento} > -40)")
            guardar_recomendacion(ticker, nombre, precio_actual, 
                                  smi_horario, smi_rapido, smi_lento, smi_semanal,
                                  "SIN COMPRA", 
                                  None, resistencia, soporte)
        
        time.sleep(0.5)
    
    print("\n" + "=" * 70)
    print(f"✅ Análisis completado")
    print(f"📈 COMPRAS: {contador_compras} (Perfectas: {contador_compras_perfectas})")
    print("=" * 70)

if __name__ == "__main__":
    analizar_todo()
