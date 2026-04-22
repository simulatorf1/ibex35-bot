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
    """
    Calcula el SMI completo devolviendo:
    - smi_smoothed: línea RÁPIDA (la que marca los giros)
    - smi_signal: línea LENTA (la de sobreventa/sobrecompra)
    """
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
    
    # Línea RÁPIDA (la que tú miras para los giros)
    smi_smoothed = smi_raw.rolling(window=smooth_period).mean()
    
    # Línea LENTA (la de sobreventa/sobrecompra)
    smi_signal = smi_smoothed.ewm(span=ema_signal_len, adjust=False).mean()
    
    return smi_smoothed, smi_signal

def obtener_smis(ticker, intervalo, periodo):
    """
    Obtiene las dos líneas del SMI (rápida y lenta)
    """
    try:
        stock = yf.Ticker(ticker)
        datos = stock.history(period=periodo, interval=intervalo)
        
        if datos.empty:
            return None, None
        
        smi_rapido, smi_lento = calcular_smi_completo(datos['High'], datos['Low'], datos['Close'])
        
        ultimo_rapido = smi_rapido.dropna().iloc[-1] if not smi_rapido.dropna().empty else None
        ultimo_lento = smi_lento.dropna().iloc[-1] if not smi_lento.dropna().empty else None
        
        # Devolver también los últimos 2 valores de la línea RÁPIDA para calcular pendiente
        if len(smi_rapido.dropna()) >= 2:
            penultimo_rapido = smi_rapido.dropna().iloc[-2]
            ultimo_rapido_val = smi_rapido.dropna().iloc[-1]
            pendiente = ultimo_rapido_val - penultimo_rapido
            giro_positivo = pendiente > 0
        else:
            pendiente = None
            giro_positivo = False
        
        return {
            "rapido_actual": round(ultimo_rapido, 2) if ultimo_rapido is not None else None,
            "lento_actual": round(ultimo_lento, 2) if ultimo_lento is not None else None,
            "pendiente": round(pendiente, 2) if pendiente is not None else None,
            "giro_positivo": giro_positivo
        }
    
    except Exception as e:
        print(f"  Error SMI: {e}")
        return None

def obtener_smi_timeframe_simple(ticker, intervalo, periodo):
    """Obtiene solo la línea LENTA del SMI para un timeframe específico"""
    try:
        stock = yf.Ticker(ticker)
        datos = stock.history(period=periodo, interval=intervalo)
        
        if datos.empty:
            return None
        
        _, smi_lento = calcular_smi_completo(datos['High'], datos['Low'], datos['Close'])
        ultimo_lento = smi_lento.dropna().iloc[-1] if not smi_lento.dropna().empty else None
        
        return round(ultimo_lento, 2) if ultimo_lento is not None else None
    
    except Exception as e:
        print(f"  Error SMI simple: {e}")
        return None

def calcular_volumen_promedio(hist, dias=30):
    """Calcula el volumen promedio de los últimos N días"""
    if len(hist) >= dias:
        return hist['Volume'].tail(dias).mean()
    return hist['Volume'].mean() if not hist.empty else 0

def identificar_resistencias(hist, precio_actual, volumen_promedio):
    """Identifica resistencias REALES"""
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
            resistencias.append({
                "precio": round(maximo, 3),
                "fecha": fila.name,
                "rechazo": rechazo,
                "volumen": volumen
            })
    
    # Agrupar por zonas
    zonas = {}
    for r in resistencias:
        precio = r["precio"]
        encontrado = False
        for zona_precio in list(zonas.keys()):
            if abs(precio - zona_precio) / zona_precio < 0.01:
                zonas[zona_precio].append(r)
                encontrado = True
                break
        if not encontrado:
            zonas[precio] = [r]
    
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
        
        rechazos = sum(1 for t in toques if t["rechazo"])
        if rechazos >= 2:
            fuerza = min(100, fuerza + 20)
        
        volumen_alto = sum(1 for t in toques if t["volumen"] > volumen_promedio)
        if volumen_alto >= 2:
            fuerza = min(100, fuerza + 10)
        
        resultado.append({
            "precio": precio,
            "fuerza": fuerza,
            "toques": toques_count
        })
    
    resultado.sort(key=lambda x: x["precio"])
    return resultado

def calcular_precio_objetivo(ticker, precio_actual):
    """Calcula la resistencia más cercana"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="90d", interval="1d")
        
        if hist.empty or len(hist) < 10:
            return None
        
        volumen_promedio = calcular_volumen_promedio(hist)
        resistencias = identificar_resistencias(hist, precio_actual, volumen_promedio)
        resistencias_fuertes = [r for r in resistencias if r["fuerza"] >= 40]
        
        if resistencias_fuertes:
            return resistencias_fuertes[0]["precio"]
        else:
            max_90d = hist['High'].max()
            return round(max_90d, 3)
        
    except Exception as e:
        print(f"    ⚠️ Error: {e}")
        return None

def verificar_recorrido_suficiente(precio_actual, precio_objetivo):
    """Verifica al menos 3% de recorrido"""
    if precio_objetivo is None or precio_actual is None:
        return False
    
    porcentaje = ((precio_objetivo - precio_actual) / precio_actual) * 100
    return porcentaje >= 3

def guardar_recomendacion(ticker, nombre, precio, smi_h, smi_d_rapido, smi_d_lento, smi_s, recomendacion, precio_obj):
    """Guarda todas las empresas en Supabase"""
    try:
        fecha_actual = datetime.now(timezone.utc).isoformat()
        
        data = {
            "fecha": fecha_actual,
            "ticker": ticker,
            "nombre_empresa": nombre,
            "precio_cierre": precio,
            "smi_horario": smi_h,
            "smi_diario": smi_d_lento,  # Guardamos el lento para la condición de sobreventa
            "smi_diario_rapido": smi_d_rapido,  # Guardamos también el rápido
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
    """Analiza todas las empresas con la lógica correcta de las DOS líneas del SMI"""
    print(f"🚀 Iniciando análisis - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)
    print("📊 CONDICIONES PARA COMPRA:")
    print("   1. SMI LENTO < -40 (sobreventa) - condición de zona")
    print("   2. SMI RÁPIDO con GIRO POSITIVO (último valor > anterior) - confirmación")
    print("   3. Recorrido suficiente (resistencia > precio + 3%)")
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
                guardar_recomendacion(ticker, nombre, None, None, None, None, None, "SIN DATOS", None)
                continue
        except Exception as e:
            print(f"  ⚠️ Error: {e}")
            guardar_recomendacion(ticker, nombre, None, None, None, None, None, "ERROR", None)
            continue
        
        # Obtener SMI Diario (rápido y lento)
        smis_diario = obtener_smis(ticker, "1d", "90d")
        
        # Obtener SMI Horario y Semanal (solo línea lenta para condiciones)
        smi_horario = obtener_smi_timeframe_simple(ticker, "1h", "7d")
        smi_semanal = obtener_smi_timeframe_simple(ticker, "1wk", "1y")
        
        if smis_diario:
            smi_rapido = smis_diario["rapido_actual"]
            smi_lento = smis_diario["lento_actual"]
            pendiente = smis_diario["pendiente"]
            giro_positivo = smis_diario["giro_positivo"]
        else:
            smi_rapido = None
            smi_lento = None
            pendiente = None
            giro_positivo = False
        
        print(f"  💰 Precio: {precio_actual}€")
        print(f"  📊 SMI LENTO (sobreventa): {smi_lento}")
        print(f"  📊 SMI RÁPIDO (giro): {smi_rapido}")
        print(f"  📊 Pendiente RÁPIDO: {pendiente} (Giro positivo: {'✅' if giro_positivo else '❌'})")
        print(f"  📊 SMI HORARIO: {smi_horario}")
        
        # ============================================
        # CONDICIÓN 1: SMI LENTO en sobreventa (< -40)
        # ============================================
        if smi_lento is not None and smi_lento < -40:
            print(f"  ✅ Condición 1: SMI LENTO en sobreventa ({smi_lento} < -40)")
            
            # ============================================
            # CONDICIÓN 2: SMI RÁPIDO con giro positivo
            # ============================================
            if giro_positivo:
                print(f"  ✅ Condición 2: SMI RÁPIDO con giro positivo detectado")
                
                # ============================================
                # CONDICIÓN 3: Calcular resistencia y verificar recorrido
                # ============================================
                print(f"  🔍 Calculando resistencia...")
                resistencia = calcular_precio_objetivo(ticker, precio_actual)
                
                recorrido_suficiente = verificar_recorrido_suficiente(precio_actual, resistencia)
                if recorrido_suficiente:
                    print(f"  ✅ Condición 3: Recorrido suficiente (mínimo 3%)")
                    
                    # ¡LAS TRES CONDICIONES SE CUMPLEN!
                    if smi_horario is not None and smi_horario < -40:
                        recomendacion = "COMPRA PERFECTA"
                        print(f"  🟢🟢 ¡COMPRA PERFECTA! (SMI horario también en sobreventa)")
                        guardar_recomendacion(ticker, nombre, precio_actual, 
                                              smi_horario, smi_rapido, smi_lento, smi_semanal,
                                              recomendacion, resistencia)
                        contador_compras_perfectas += 1
                        contador_compras += 1
                    else:
                        recomendacion = "COMPRA (esperar momento)"
                        print(f"  🟢 ¡COMPRA! (esperar momento horario)")
                        guardar_recomendacion(ticker, nombre, precio_actual, 
                                              smi_horario, smi_rapido, smi_lento, smi_semanal,
                                              recomendacion, resistencia)
                        contador_compras += 1
                else:
                    print(f"  ❌ Condición 3: Recorrido insuficiente (resistencia demasiado cerca)")
                    guardar_recomendacion(ticker, nombre, precio_actual, 
                                          smi_horario, smi_rapido, smi_lento, smi_semanal,
                                          "SIN COMPRA (recorrido insuficiente)", None)
            else:
                print(f"  ❌ Condición 2: SMI RÁPIDO sin giro positivo (pendiente {pendiente})")
                guardar_recomendacion(ticker, nombre, precio_actual, 
                                      smi_horario, smi_rapido, smi_lento, smi_semanal,
                                      "SIN COMPRA (SMI sin giro)", None)
        else:
            print(f"  ❌ Condición 1: SMI LENTO NO en sobreventa ({smi_lento} > -40)")
            guardar_recomendacion(ticker, nombre, precio_actual, 
                                  smi_horario, smi_rapido, smi_lento, smi_semanal,
                                  "SIN COMPRA", None)
        
        time.sleep(0.5)
    
    print("\n" + "=" * 70)
    print(f"✅ Análisis completado")
    print(f"📈 COMPRAS: {contador_compras} (Perfectas: {contador_compras_perfectas})")
    print("=" * 70)

if __name__ == "__main__":
    analizar_todo()
