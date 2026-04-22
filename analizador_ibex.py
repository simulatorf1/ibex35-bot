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

def identificar_todos_los_niveles(ticker, precio_actual):
    """
    Identifica TODOS los niveles importantes (soportes y resistencias)
    basados en MÁXIMOS y MÍNIMOS de CADA VELA en los últimos 90 días
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="90d", interval="1d")
        
        if hist.empty or len(hist) < 20:
            return [], []
        
        volumen_promedio = hist['Volume'].tail(30).mean()
        
        # ============================================
        # RECOPILAR TODOS LOS MÁXIMOS (resistencias potenciales)
        # ============================================
        maximos_con_datos = []
        for i in range(len(hist)):
            fila = hist.iloc[i]
            maximo = round(fila['High'], 3)
            cierre = round(fila['Close'], 3)
            volumen = fila['Volume']
            
            # Rechazo: cierre al menos 2% por debajo del máximo
            rechazo = (maximo - cierre) / maximo > 0.02
            
            maximos_con_datos.append({
                "precio": maximo,
                "fecha": fila.name,
                "rechazo": rechazo,
                "volumen": volumen
            })
        
        # ============================================
        # RECOPILAR TODOS LOS MÍNIMOS (soportes potenciales)
        # ============================================
        minimos_con_datos = []
        for i in range(len(hist)):
            fila = hist.iloc[i]
            minimo = round(fila['Low'], 3)
            cierre = round(fila['Close'], 3)
            volumen = fila['Volume']
            
            # Rebote: cierre al menos 2% por encima del mínimo
            rebote = (cierre - minimo) / minimo > 0.02
            
            minimos_con_datos.append({
                "precio": minimo,
                "fecha": fila.name,
                "rebote": rebote,
                "volumen": volumen
            })
        
        # ============================================
        # AGRUPAR POR ZONAS (tolerancia ±2%)
        # ============================================
        TOLERANCIA = 0.02  # 2%
        
        def agrupar_por_zona(datos, es_maximo):
            zonas = {}
            for d in datos:
                precio = d["precio"]
                encontrado = False
                for zona_precio in list(zonas.keys()):
                    if abs(precio - zona_precio) / zona_precio < TOLERANCIA:
                        zonas[zona_precio].append(d)
                        encontrado = True
                        break
                if not encontrado:
                    zonas[precio] = [d]
            
            # Calcular estadísticas de cada zona
            resultados = []
            for precio, toques in zonas.items():
                toques_count = len(toques)
                
                if es_maximo:
                    rechazos = sum(1 for t in toques if t["rechazo"])
                    volumen_total = sum(t["volumen"] for t in toques)
                    
                    # Fuerza (0-100)
                    fuerza = 30
                    if toques_count >= 4:
                        fuerza = 80
                    elif toques_count == 3:
                        fuerza = 65
                    elif toques_count == 2:
                        fuerza = 50
                    
                    if rechazos >= 2:
                        fuerza = min(100, fuerza + 15)
                    if volumen_total / toques_count > volumen_promedio:
                        fuerza = min(100, fuerza + 10)
                    
                    resultados.append({
                        "precio": precio,
                        "toques": toques_count,
                        "rechazos": rechazos,
                        "fuerza": fuerza
                    })
                else:
                    rebotes = sum(1 for t in toques if t["rebote"])
                    volumen_total = sum(t["volumen"] for t in toques)
                    
                    fuerza = 30
                    if toques_count >= 4:
                        fuerza = 80
                    elif toques_count == 3:
                        fuerza = 65
                    elif toques_count == 2:
                        fuerza = 50
                    
                    if rebotes >= 2:
                        fuerza = min(100, fuerza + 15)
                    if volumen_total / toques_count > volumen_promedio:
                        fuerza = min(100, fuerza + 10)
                    
                    resultados.append({
                        "precio": precio,
                        "toques": toques_count,
                        "rebotes": rebotes,
                        "fuerza": fuerza
                    })
            
            return resultados
        
        todas_resistencias = agrupar_por_zona(maximos_con_datos, es_maximo=True)
        todos_soportes = agrupar_por_zona(minimos_con_datos, es_maximo=False)
        
        # ============================================
        # FILTRAR POR PRECIO ACTUAL
        # ============================================
        resistencias_arriba = [r for r in todas_resistencias if r["precio"] > precio_actual]
        soportes_abajo = [s for s in todos_soportes if s["precio"] < precio_actual]
        
        # Ordenar
        resistencias_arriba.sort(key=lambda x: x["precio"])  # de más cercana a más lejana
        soportes_abajo.sort(key=lambda x: x["precio"], reverse=True)  # de más cercano a más lejano
        
        # ============================================
        # CONVERTIR RESISTENCIAS SUPERADAS EN SOPORTES
        # ============================================
        for r in resistencias_arriba[:]:
            # Ver si esta resistencia fue superada alguna vez
            precio_r = r["precio"]
            superada = False
            for i in range(len(hist)):
                if hist.iloc[i]['Close'] > precio_r:
                    superada = True
                    break
            
            if superada:
                # Mover a soportes
                soportes_abajo.append({
                    "precio": precio_r,
                    "toques": r["toques"],
                    "rebotes": r.get("rechazos", 0),
                    "fuerza": r["fuerza"] * 0.8,
                    "nota": "ANTIGUA RESISTENCIA"
                })
                resistencias_arriba.remove(r)
        
        # Reordenar soportes después de añadir los convertidos
        soportes_abajo.sort(key=lambda x: x["precio"], reverse=True)
        
        # Mostrar TODOS los niveles encontrados
        print(f"\n  📊 NIVELES ENCONTRADOS (últimos 90 días):")
        print(f"  {'='*50}")
        
        print(f"  📉 SOPORTES (por debajo de {precio_actual}€):")
        for s in soportes_abajo:
            nota = s.get("nota", "")
            print(f"     💪 {s['precio']}€ - {s['toques']} toques, fuerza: {s['fuerza']} {nota}")
        
        print(f"\n  📈 RESISTENCIAS (por encima de {precio_actual}€):")
        for r in resistencias_arriba:
            print(f"     💪 {r['precio']}€ - {r['toques']} toques, fuerza: {r['fuerza']}")
        
        # Resistencia principal (la más cercana con fuerza suficiente)
        resistencia_principal = None
        for r in resistencias_arriba:
            if r["fuerza"] >= 40:  # Solo resistencias con fuerza mínima
                distancia = ((r["precio"] - precio_actual) / precio_actual) * 100
                if distancia >= 2:  # Al menos 2% de recorrido
                    resistencia_principal = r["precio"]
                    break
        
        return soportes_abajo, resistencias_arriba, resistencia_principal
    
    except Exception as e:
        print(f"  Error identificando niveles: {e}")
        return [], [], None

def guardar_recomendacion(ticker, nombre, precio, smi_h, smi_rapido, smi_w, 
                          recomendacion, precio_obj):
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
        
        print(f"  💾 Guardado: {nombre}")
        
    except Exception as e:
        print(f"  ❌ Error guardando: {e}")

def analizar_todo():
    """Analiza todas las empresas con la lógica correcta"""
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
        
        # Identificar TODOS los niveles importantes
        soportes, resistencias, resistencia_principal = identificar_todos_los_niveles(ticker, precio_actual)
        
        print(f"\n  💰 Precio actual: {precio_actual}€")
        print(f"  📊 SMI RÁPIDO: {smi_rapido}")
        print(f"  📊 Pendiente: {pendiente} (Giro: {'✅' if giro_positivo else '❌'})")
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
                # CONDICIÓN 3: Resistencia válida
                # ============================================
                if resistencia_principal:
                    recorrido = ((resistencia_principal - precio_actual) / precio_actual) * 100
                    print(f"  📊 Resistencia principal: {resistencia_principal}€ (recorrido: {recorrido:.2f}%)")
                    
                    if recorrido >= 2:
                        print(f"  ✅ Condición 3: Recorrido suficiente")
                        
                        if smi_horario is not None and smi_horario < -40:
                            recomendacion = "COMPRA PERFECTA"
                            print(f"  🟢🟢 ¡COMPRA PERFECTA!")
                            guardar_recomendacion(ticker, nombre, precio_actual, 
                                                  smi_horario, smi_rapido, smi_semanal,
                                                  recomendacion, resistencia_principal)
                            contador_compras_perfectas += 1
                            contador_compras += 1
                        else:
                            recomendacion = "COMPRA (esperar momento)"
                            print(f"  🟢 ¡COMPRA!")
                            guardar_recomendacion(ticker, nombre, precio_actual, 
                                                  smi_horario, smi_rapido, smi_semanal,
                                                  recomendacion, resistencia_principal)
                            contador_compras += 1
                    else:
                        print(f"  ❌ Condición 3: Recorrido insuficiente")
                        guardar_recomendacion(ticker, nombre, precio_actual, 
                                              smi_horario, smi_rapido, smi_semanal,
                                              "SIN COMPRA (recorrido insuficiente)", None)
                else:
                    print(f"  ❌ Condición 3: No hay resistencia válida")
                    guardar_recomendacion(ticker, nombre, precio_actual, 
                                          smi_horario, smi_rapido, smi_semanal,
                                          "SIN COMPRA (sin resistencia)", None)
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
