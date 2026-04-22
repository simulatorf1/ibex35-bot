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

def identificar_niveles(ticker, precio_actual):
    """
    Identifica SOPORTES y RESISTENCIAS con tolerancia del 0.3%
    Solo muestra niveles con al menos 2 toques
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="90d", interval="1d")
        
        if hist.empty or len(hist) < 20:
            return [], []
        
        TOLERANCIA = 0.003  # 0.3%
        MIN_TOQUES = 2      # Mínimo 2 toques para considerar un nivel
        
        volumen_promedio = hist['Volume'].tail(30).mean()
        
        # ============================================
        # RECOPILAR TODOS LOS MÁXIMOS
        # ============================================
        maximos = []
        for i in range(len(hist)):
            fila = hist.iloc[i]
            maximo = round(fila['High'], 3)
            cierre = round(fila['Close'], 3)
            volumen = fila['Volume']
            
            rechazo = (maximo - cierre) / maximo > 0.02
            
            maximos.append({
                "precio": maximo,
                "rechazo": rechazo,
                "volumen": volumen
            })
        
        # ============================================
        # RECOPILAR TODOS LOS MÍNIMOS
        # ============================================
        minimos = []
        for i in range(len(hist)):
            fila = hist.iloc[i]
            minimo = round(fila['Low'], 3)
            cierre = round(fila['Close'], 3)
            volumen = fila['Volume']
            
            rebote = (cierre - minimo) / minimo > 0.02
            
            minimos.append({
                "precio": minimo,
                "rebote": rebote,
                "volumen": volumen
            })
        
        # ============================================
        # AGRUPAR POR ZONAS CON TOLERANCIA 0.3%
        # ============================================
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
            
            # Calcular estadísticas
            resultados = []
            for precio, toques in zonas.items():
                toques_count = len(toques)
                
                if toques_count < MIN_TOQUES:
                    continue
                
                if es_maximo:
                    rechazos = sum(1 for t in toques if t["rechazo"])
                    volumen_total = sum(t["volumen"] for t in toques)
                    
                    # Fuerza (0-100)
                    fuerza = 30
                    if toques_count >= 5:
                        fuerza = 90
                    elif toques_count >= 4:
                        fuerza = 75
                    elif toques_count >= 3:
                        fuerza = 60
                    elif toques_count >= 2:
                        fuerza = 45
                    
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
                    if toques_count >= 5:
                        fuerza = 90
                    elif toques_count >= 4:
                        fuerza = 75
                    elif toques_count >= 3:
                        fuerza = 60
                    elif toques_count >= 2:
                        fuerza = 45
                    
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
        
        todas_resistencias = agrupar_por_zona(maximos, es_maximo=True)
        todos_soportes = agrupar_por_zona(minimos, es_maximo=False)
        
        # ============================================
        # CLASIFICAR POR PRECIO ACTUAL
        # ============================================
        resistencias = [r for r in todas_resistencias if r["precio"] > precio_actual]
        soportes = [s for s in todos_soportes if s["precio"] < precio_actual]
        
        # Ordenar
        resistencias.sort(key=lambda x: x["precio"])  # de más cercana a más lejana
        soportes.sort(key=lambda x: x["precio"], reverse=True)  # de más cercano a más lejano
        
        return soportes, resistencias
    
    except Exception as e:
        print(f"  Error identificando niveles: {e}")
        return [], []

def guardar_recomendacion(ticker, nombre, precio, smi_h, smi_rapido, smi_w, recomendacion, precio_obj):
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
        
    except Exception as e:
        print(f"  ❌ Error guardando: {e}")

def analizar_todo():
    """Analiza todas las empresas con la lógica correcta"""
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
        
        # Identificar TODOS los niveles
        soportes, resistencias = identificar_niveles(ticker, precio_actual)
        
        print(f"\n  💰 Precio actual: {precio_actual}€")
        print(f"  📊 SMI RÁPIDO: {smi_rapido}")
        print(f"  📊 Pendiente: {pendiente} (Giro: {'✅' if giro_positivo else '❌'})")
        print(f"  📊 SMI HORARIO: {smi_horario}")
        
        # Mostrar TODOS los niveles encontrados
        print(f"\n  📊 NIVELES ENCONTRADOS (tolerancia 0.3%, mínimo {2} toques):")
        print(f"  {'='*50}")
        
        print(f"  📉 SOPORTES (por debajo de {precio_actual}€):")
        if soportes:
            for s in soportes:
                print(f"     💪 {s['precio']}€ - {s['toques']} toques, fuerza: {s['fuerza']}")
        else:
            print(f"     ❌ No hay soportes claros")
        
        print(f"\n  📈 RESISTENCIAS (por encima de {precio_actual}€):")
        if resistencias:
            for r in resistencias:
                print(f"     💪 {r['precio']}€ - {r['toques']} toques, fuerza: {r['fuerza']}")
        else:
            print(f"     ❌ No hay resistencias claras")
        
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
                # CONDICIÓN 3: Buscar resistencia válida (más cercana con recorrido >= 3%)
                # ============================================
                resistencia_valida = None
                for r in resistencias:
                    recorrido = ((r["precio"] - precio_actual) / precio_actual) * 100
                    if recorrido >= 3:
                        resistencia_valida = r["precio"]
                        print(f"  📊 Resistencia válida: {resistencia_valida}€ (recorrido: {recorrido:.2f}%)")
                        break
                
                if resistencia_valida:
                    print(f"  ✅ Condición 3: Resistencia válida encontrada")
                    
                    if smi_horario is not None and smi_horario < -40:
                        recomendacion = "COMPRA PERFECTA"
                        print(f"  🟢🟢 ¡COMPRA PERFECTA!")
                        guardar_recomendacion(ticker, nombre, precio_actual, 
                                              smi_horario, smi_rapido, smi_semanal,
                                              recomendacion, resistencia_valida)
                        contador_compras_perfectas += 1
                        contador_compras += 1
                    else:
                        recomendacion = "COMPRA (esperar momento)"
                        print(f"  🟢 ¡COMPRA!")
                        guardar_recomendacion(ticker, nombre, precio_actual, 
                                              smi_horario, smi_rapido, smi_semanal,
                                              recomendacion, resistencia_valida)
                        contador_compras += 1
                else:
                    print(f"  ❌ Condición 3: No hay resistencia válida (recorrido < 3%)")
                    guardar_recomendacion(ticker, nombre, precio_actual, 
                                          smi_horario, smi_rapido, smi_semanal,
                                          "SIN COMPRA (sin resistencia válida)", None)
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
