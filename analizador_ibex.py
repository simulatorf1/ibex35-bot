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

def identificar_niveles_importantes(ticker, precio_actual):
    """
    Identifica SOPORTES y RESISTENCIAS REALES con:
    - Máximos y mínimos de CADA VELA (no cierres)
    - Rechazos (cierre bajo vs máximo) y rebotes (cierre alto vs mínimo)
    - Volumen significativo
    - Agrupación por zonas (±1%)
    - Conversión de resistencia superada → soporte
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="90d", interval="1d")
        
        if hist.empty or len(hist) < 20:
            return [], [], None, None
        
        volumen_promedio = hist['Volume'].tail(30).mean()
        
        # ============================================
        # PASO 1: Recopilar candidatos a resistencia (máximos)
        # ============================================
        candidatos_resistencias = []
        fechas_superacion = set()
        
        for i in range(len(hist)):
            fila = hist.iloc[i]
            maximo = round(fila['High'], 3)
            cierre = round(fila['Close'], 3)
            volumen = fila['Volume']
            
            # Rechazo: el cierre está al menos 2% por debajo del máximo
            rechazo = (maximo - cierre) / maximo > 0.02
            
            # Volumen significativo
            volumen_alto = volumen > (volumen_promedio * 0.8)
            
            if rechazo or volumen_alto:
                candidatos_resistencias.append({
                    "precio": maximo,
                    "fecha": fila.name,
                    "rechazo": rechazo,
                    "volumen": volumen
                })
            
            # Detectar si se superó una resistencia (cierre por encima)
            # Esto lo haremos después de agrupar
        
        # ============================================
        # PASO 2: Recopilar candidatos a soporte (mínimos)
        # ============================================
        candidatos_soportes = []
        
        for i in range(len(hist)):
            fila = hist.iloc[i]
            minimo = round(fila['Low'], 3)
            cierre = round(fila['Close'], 3)
            volumen = fila['Volume']
            
            # Rebote: el cierre está al menos 2% por encima del mínimo
            rebote = (cierre - minimo) / minimo > 0.02
            
            # Volumen significativo
            volumen_alto = volumen > (volumen_promedio * 0.8)
            
            if rebote or volumen_alto:
                candidatos_soportes.append({
                    "precio": minimo,
                    "fecha": fila.name,
                    "rebote": rebote,
                    "volumen": volumen
                })
        
        # ============================================
        # PASO 3: Agrupar resistencias por zona (±1%)
        # ============================================
        zonas_resistencia = {}
        for r in candidatos_resistencias:
            precio = r["precio"]
            encontrado = False
            for zona_precio in list(zonas_resistencia.keys()):
                if abs(precio - zona_precio) / zona_precio < 0.01:
                    zonas_resistencia[zona_precio].append(r)
                    encontrado = True
                    break
            if not encontrado:
                zonas_resistencia[precio] = [r]
        
        # Calcular fuerza de cada zona de resistencia
        resistencias = []
        for precio, toques in zonas_resistencia.items():
            toques_count = len(toques)
            rechazos = sum(1 for t in toques if t["rechazo"])
            volumen_total = sum(t["volumen"] for t in toques)
            volumen_promedio_zona = volumen_total / toques_count
            
            # Fuerza (0-100)
            fuerza = 0
            if toques_count >= 3:
                fuerza = 70
            elif toques_count == 2:
                fuerza = 50
            else:
                fuerza = 30
            
            if rechazos >= 2:
                fuerza = min(100, fuerza + 20)
            if volumen_promedio_zona > volumen_promedio:
                fuerza = min(100, fuerza + 10)
            
            resistencias.append({
                "precio": precio,
                "fuerza": fuerza,
                "toques": toques_count,
                "rechazos": rechazos
            })
        
        # ============================================
        # PASO 4: Agrupar soportes por zona (±1%)
        # ============================================
        zonas_soporte = {}
        for s in candidatos_soportes:
            precio = s["precio"]
            encontrado = False
            for zona_precio in list(zonas_soporte.keys()):
                if abs(precio - zona_precio) / zona_precio < 0.01:
                    zonas_soporte[zona_precio].append(s)
                    encontrado = True
                    break
            if not encontrado:
                zonas_soporte[precio] = [s]
        
        # Calcular fuerza de cada zona de soporte
        soportes = []
        for precio, toques in zonas_soporte.items():
            toques_count = len(toques)
            rebotes = sum(1 for t in toques if t["rebote"])
            volumen_total = sum(t["volumen"] for t in toques)
            volumen_promedio_zona = volumen_total / toques_count
            
            fuerza = 0
            if toques_count >= 3:
                fuerza = 70
            elif toques_count == 2:
                fuerza = 50
            else:
                fuerza = 30
            
            if rebotes >= 2:
                fuerza = min(100, fuerza + 20)
            if volumen_promedio_zona > volumen_promedio:
                fuerza = min(100, fuerza + 10)
            
            soportes.append({
                "precio": precio,
                "fuerza": fuerza,
                "toques": toques_count,
                "rebotes": rebotes
            })
        
        # ============================================
        # PASO 5: Verificar resistencias que fueron superadas (ahora son soporte)
        # ============================================
        for r in resistencias[:]:
            precio_r = r["precio"]
            # Ver si alguna vez se superó (cierre por encima)
            superada = False
            for i in range(len(hist)):
                if hist.iloc[i]['Close'] > precio_r:
                    superada = True
                    break
            
            if superada:
                # Esta resistencia ahora es soporte
                soportes.append({
                    "precio": precio_r,
                    "fuerza": r["fuerza"] * 0.8,  # Pierde un poco de fuerza
                    "toques": r["toques"],
                    "rebotes": 0,
                    "nota": "ANTIGUA RESISTENCIA"
                })
                # La eliminamos de resistencias
                resistencias.remove(r)
        
        # ============================================
        # PASO 6: Filtrar y ordenar
        # ============================================
        # Soportes: solo los que están por DEBAJO del precio actual
        soportes_validos = [s for s in soportes if s["precio"] < precio_actual]
        soportes_validos.sort(key=lambda x: x["precio"], reverse=True)  # Los más cercanos primero
        
        # Resistencias: solo los que están por ENCIMA del precio actual
        resistencias_validas = [r for r in resistencias if r["precio"] > precio_actual]
        resistencias_validas.sort(key=lambda x: x["precio"])  # Los más cercanos primero
        
        # Tomar los 2 más importantes de cada lado
        soportes_final = soportes_validos[:2]
        resistencias_final = resistencias_validas[:2]
        
        # Nivel principal para objetivo
        resistencia_principal = resistencias_final[0]["precio"] if resistencias_final else None
        soporte_principal = soportes_final[0]["precio"] if soportes_final else None
        
        # Mostrar detalles
        for s in soportes_final:
            print(f"     📉 SOPORTE: {s['precio']}€ (toques: {s['toques']}, fuerza: {s['fuerza']})")
        for r in resistencias_final:
            print(f"     📈 RESISTENCIA: {r['precio']}€ (toques: {r['toques']}, fuerza: {r['fuerza']})")
        
        return soportes_final, resistencias_final, soporte_principal, resistencia_principal
    
    except Exception as e:
        print(f"  Error en niveles: {e}")
        return [], [], None, None

def guardar_recomendacion(ticker, nombre, precio, smi_h, smi_rapido, smi_w, 
                          recomendacion, precio_obj, soportes, resistencias):
    """Guarda todas las empresas en Supabase"""
    try:
        fecha_actual = datetime.now(timezone.utc).isoformat()
        
        # Convertir listas a string para guardar
        soportes_str = ", ".join([str(s["precio"]) for s in soportes]) if soportes else None
        resistencias_str = ", ".join([str(r["precio"]) for r in resistencias]) if resistencias else None
        
        data = {
            "fecha": fecha_actual,
            "ticker": ticker,
            "nombre_empresa": nombre,
            "precio_cierre": precio,
            "smi_horario": smi_h if smi_h else None,
            "smi_diario": smi_rapido,
            "smi_semanal": smi_w if smi_w else None,
            "recomendacion": recomendacion,
            "precio_objetivo": precio_obj if precio_obj else None,
            "soportes": soportes_str,
            "resistencias": resistencias_str
        }
        
        supabase.table("recomendaciones").insert(data).execute()
        
        print(f"  💾 Guardado: {nombre}")
        
    except Exception as e:
        print(f"  ❌ Error guardando: {e}")

def analizar_todo():
    """Analiza todas las empresas con la lógica correcta de niveles"""
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
        
        # Obtener SMI RÁPIDO
        smi_rapido, pendiente, giro_positivo = obtener_smi_rapido_con_pendiente(ticker)
        
        # Obtener SMI horario y semanal
        smi_horario, smi_semanal = obtener_smi_horario_semanal(ticker)
        
        # Identificar SOPORTES y RESISTENCIAS reales
        print(f"  🔍 Identificando niveles importantes (90 días de datos)...")
        soportes, resistencias, soporte_principal, resistencia_principal = identificar_niveles_importantes(ticker, precio_actual)
        
        print(f"  💰 Precio actual: {precio_actual}€")
        print(f"  📊 SMI RÁPIDO: {smi_rapido} (pendiente: {pendiente}, giro: {'✅' if giro_positivo else '❌'})")
        print(f"  📊 SMI HORARIO: {smi_horario}")
        
        # ============================================
        # CONDICIÓN 1: SMI en sobreventa
        # ============================================
        if smi_rapido is not None and smi_rapido < -40:
            print(f"  ✅ Condición 1: SMI en sobreventa")
            
            # ============================================
            # CONDICIÓN 2: Giro positivo
            # ============================================
            if giro_positivo:
                print(f"  ✅ Condición 2: Giro positivo")
                
                # ============================================
                # CONDICIÓN 3: Resistencia válida (>3% de recorrido)
                # ============================================
                if resistencia_principal:
                    recorrido = ((resistencia_principal - precio_actual) / precio_actual) * 100
                    print(f"  📊 Resistencia principal: {resistencia_principal}€ (recorrido: {recorrido:.2f}%)")
                    
                    if recorrido >= 3:
                        print(f"  ✅ Condición 3: Recorrido suficiente ({recorrido:.2f}% >= 3%)")
                        
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
                        print(f"  ❌ Condición 3: Recorrido insuficiente ({recorrido:.2f}% < 3%)")
                        guardar_recomendacion(ticker, nombre, precio_actual, 
                                              smi_horario, smi_rapido, smi_semanal,
                                              "SIN COMPRA (recorrido insuficiente)", 
                                              None, soportes, resistencias)
                else:
                    print(f"  ❌ Condición 3: No hay resistencia válida por encima")
                    guardar_recomendacion(ticker, nombre, precio_actual, 
                                          smi_horario, smi_rapido, smi_semanal,
                                          "SIN COMPRA (sin resistencia)", 
                                          None, soportes, resistencias)
            else:
                print(f"  ❌ Condición 2: SMI sin giro positivo")
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
