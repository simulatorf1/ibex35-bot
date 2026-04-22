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
    """Calcula SOLO la línea RÁPIDA del SMI (la que marca giros)"""
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
    
    # Línea RÁPIDA
    smi_rapido = smi_raw.rolling(window=smooth_period).mean()
    
    return smi_rapido

def obtener_smi_rapido_con_pendiente(ticker):
    """Obtiene el SMI rápido y calcula su pendiente (giro)"""
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
    """Obtiene SMI horario y semanal (opcional, si falla da None)"""
    try:
        stock = yf.Ticker(ticker)
        
        # Horario
        datos_h = stock.history(period="7d", interval="1h")
        smi_h = None
        if not datos_h.empty and len(datos_h) > 5:
            smi_h_temp = calcular_smi_rapido(datos_h['High'], datos_h['Low'], datos_h['Close'])
            smi_h_clean = smi_h_temp.dropna()
            if not smi_h_clean.empty:
                smi_h = round(smi_h_clean.iloc[-1], 2)
        
        # Semanal
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

def calcular_soportes_y_resistencias(ticker, precio_actual):
    """
    Calcula 2 SOPORTES por debajo y 2 RESISTENCIAS por encima
    Si una resistencia está a menos del 2%, la descarta y busca la siguiente
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="90d", interval="1d")
        
        if hist.empty or len(hist) < 10:
            return [], [], None, None
        
        volumen_promedio = hist['Volume'].tail(30).mean()
        
        # Recopilar todos los máximos y mínimos significativos
        maximos = []
        minimos = []
        
        for i in range(len(hist)):
            fila = hist.iloc[i]
            maximo = fila['High']
            minimo = fila['Low']
            cierre = fila['Close']
            volumen = fila['Volume']
            
            # Máximos con rechazo o volumen significativo
            if maximo > precio_actual:
                rechazo = (maximo - cierre) / maximo > 0.02
                volumen_significativo = volumen > (volumen_promedio * 0.8)
                if rechazo or volumen_significativo:
                    maximos.append(round(maximo, 3))
            
            # Mínimos con rebote o volumen significativo
            if minimo < precio_actual:
                rebote = (cierre - minimo) / minimo > 0.02
                volumen_significativo = volumen > (volumen_promedio * 0.8)
                if rebote or volumen_significativo:
                    minimos.append(round(minimo, 3))
        
        # Eliminar duplicados y ordenar
        maximos = sorted(list(set(maximos)))
        minimos = sorted(list(set(minimos)), reverse=True)
        
        # ============================================
        # RESISTENCIAS: buscar las que estén a más del 2%
        # ============================================
        resistencias_validas = []
        for r in maximos:
            distancia_pct = ((r - precio_actual) / precio_actual) * 100
            if distancia_pct >= 2:  # Solo si está al menos a 2%
                resistencias_validas.append(r)
        
        # Tomar las 2 primeras resistencias válidas
        resistencias = resistencias_validas[:2]
        
        # Si no hay resistencias válidas, usar el máximo de 90 días
        if not resistencias:
            max_90d = round(hist['High'].max(), 3)
            if max_90d > precio_actual:
                resistencias = [max_90d]
        
        # ============================================
        # SOPORTES: tomar los 2 más cercanos por debajo
        # ============================================
        soportes = minimos[:2] if minimos else []
        
        # Si no hay soportes, usar el mínimo de 90 días
        if not soportes:
            min_90d = round(hist['Low'].min(), 3)
            if min_90d < precio_actual:
                soportes = [min_90d]
        
        # Para mostrar en pantalla
        resistencia_principal = resistencias[0] if resistencias else None
        soporte_principal = soportes[0] if soportes else None
        
        return soportes, resistencias, soporte_principal, resistencia_principal
    
    except Exception as e:
        print(f"  Error niveles: {e}")
        return [], [], None, None

def guardar_recomendacion(ticker, nombre, precio, smi_h, smi_rapido, smi_w, 
                          recomendacion, precio_obj, soportes, resistencias):
    """Guarda todas las empresas en Supabase"""
    try:
        fecha_actual = datetime.now(timezone.utc).isoformat()
        
        data = {
            "fecha": fecha_actual,
            "ticker": ticker,
            "nombre_empresa": nombre,
            "precio_cierre": precio,
            "smi_horario": smi_h if smi_h else None,
            "smi_diario": smi_rapido,  # Ahora guardamos el rápido como principal
            "smi_semanal": smi_w if smi_w else None,
            "recomendacion": recomendacion,
            "precio_objetivo": precio_obj if precio_obj else None
        }
        
        supabase.table("recomendaciones").insert(data).execute()
        
        print(f"  💾 Guardado: {nombre}")
        print(f"     📉 Soportes: {soportes if soportes else 'No hay'} €")
        print(f"     📈 Resistencias: {resistencias if resistencias else 'No hay'} €")
        
        if "COMPRA" in recomendacion and precio_obj:
            recorrido = ((precio_obj - precio) / precio) * 100
            print(f"     🎯 Objetivo: {precio_obj}€ | Recorrido: {recorrido:.1f}%")
        
    except Exception as e:
        print(f"  ❌ Error guardando: {e}")

def analizar_todo():
    """Analiza todas las empresas con la lógica CORRECTA (solo SMI rápido)"""
    print(f"🚀 Iniciando análisis - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)
    print("📊 CONDICIONES PARA COMPRA:")
    print("   1. SMI RÁPIDO < -40 (sobreventa)")
    print("   2. SMI RÁPIDO con GIRO POSITIVO (pendiente > 0)")
    print("   3. Resistencia válida a más del 2% del precio actual")
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
        
        # Obtener SMI RÁPIDO y su pendiente
        smi_rapido, pendiente, giro_positivo = obtener_smi_rapido_con_pendiente(ticker)
        
        # Obtener SMI horario y semanal (opcional)
        smi_horario, smi_semanal = obtener_smi_horario_semanal(ticker)
        
        # Calcular soportes y resistencias
        soportes, resistencias, soporte_principal, resistencia_principal = calcular_soportes_y_resistencias(ticker, precio_actual)
        
        print(f"  💰 Precio: {precio_actual}€")
        print(f"  📊 SMI RÁPIDO: {smi_rapido}")
        print(f"  📊 Pendiente: {pendiente} (Giro positivo: {'✅' if giro_positivo else '❌'})")
        print(f"  📊 SMI HORARIO: {smi_horario}")
        print(f"  📉 SOPORTES (por debajo): {soportes if soportes else 'No hay'} €")
        print(f"  📈 RESISTENCIAS (por encima): {resistencias if resistencias else 'No hay'} €")
        
        # ============================================
        # CONDICIÓN 1: SMI RÁPIDO en sobreventa (< -40)
        # ============================================
        if smi_rapido is not None and smi_rapido < -40:
            print(f"  ✅ Condición 1: SMI en sobreventa ({smi_rapido} < -40)")
            
            # ============================================
            # CONDICIÓN 2: Giro positivo
            # ============================================
            if giro_positivo:
                print(f"  ✅ Condición 2: Giro positivo detectado")
                
                # ============================================
                # CONDICIÓN 3: ¿Hay resistencia válida?
                # ============================================
                if resistencia_principal:
                    recorrido = ((resistencia_principal - precio_actual) / precio_actual) * 100
                    print(f"  📊 Resistencia principal: {resistencia_principal}€ (recorrido: {recorrido:.2f}%)")
                    
                    # La resistencia ya está filtrada al menos al 2%
                    if smi_horario is not None and smi_horario < -40:
                        recomendacion = "COMPRA PERFECTA"
                        print(f"  🟢🟢 ¡COMPRA PERFECTA!")
                        guardar_recomendacion(ticker, nombre, precio_actual, 
                                              smi_horario, smi_rapido, smi_semanal,
                                              recomendacion, resistencia_principal, 
                                              soportes, resistencias)
                        contador_compras_perfectas += 1
                        contador_compras += 1
                    else:
                        recomendacion = "COMPRA (esperar momento)"
                        print(f"  🟢 ¡COMPRA!")
                        guardar_recomendacion(ticker, nombre, precio_actual, 
                                              smi_horario, smi_rapido, smi_semanal,
                                              recomendacion, resistencia_principal,
                                              soportes, resistencias)
                        contador_compras += 1
                else:
                    print(f"  ❌ Condición 3: No hay resistencia válida (todas están a menos del 2%)")
                    guardar_recomendacion(ticker, nombre, precio_actual, 
                                          smi_horario, smi_rapido, smi_semanal,
                                          "SIN COMPRA (sin resistencia válida)", 
                                          None, soportes, resistencias)
            else:
                print(f"  ❌ Condición 2: SMI sin giro positivo (pendiente {pendiente})")
                guardar_recomendacion(ticker, nombre, precio_actual, 
                                      smi_horario, smi_rapido, smi_semanal,
                                      "SIN COMPRA (SMI sin giro)", 
                                      None, soportes, resistencias)
        else:
            print(f"  ❌ Condición 1: SMI NO en sobreventa ({smi_rapido} > -40)")
            guardar_recomendacion(ticker, nombre, precio_actual, 
                                  smi_horario, smi_rapido, smi_semanal,
                                  "SIN COMPRA", 
                                  None, soportes, resistencias)
        
        time.sleep(0.5)
    
    print("\n" + "=" * 70)
    print(f"✅ Análisis completado")
    print(f"📈 COMPRAS: {contador_compras} (Perfectas: {contador_compras_perfectas})")
    print("=" * 70)

if __name__ == "__main__":
    analizar_todo()
