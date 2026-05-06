import yfinance as yf
import pandas as pd
import numpy as np
from supabase import create_client, Client
from datetime import datetime
import time
import os
import pytz

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
    ("ADX.MC", "Audax"),
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

def obtener_smi_con_pendiente(ticker, period, interval):
    """Obtiene el SMI y su pendiente"""
    try:
        stock = yf.Ticker(ticker)
        datos = stock.history(period=period, interval=interval)
        
        if datos.empty or len(datos) < 10:
            return None, None, False
        
        smi = calcular_smi_rapido(datos['High'], datos['Low'], datos['Close'])
        smi_clean = smi.dropna()
        
        if len(smi_clean) < 2:
            return None, None, False
        
        ultimo = round(smi_clean.iloc[-1], 2)
        penultimo = smi_clean.iloc[-2]
        pendiente = round(ultimo - penultimo, 2)
        giro_positivo = pendiente > 0
        
        return ultimo, pendiente, giro_positivo
    
    except Exception as e:
        print(f" Error SMI: {e}")
        return None, None, False

def obtener_smi_4h(ticker):
    """Obtiene SMI cada 4 horas"""
    try:
        stock = yf.Ticker(ticker)
        datos = stock.history(period="10d", interval="4h")
        
        if datos.empty or len(datos) < 5:
            return None
        
        smi_temp = calcular_smi_rapido(datos['High'], datos['Low'], datos['Close'])
        smi_clean = smi_temp.dropna()
        
        if not smi_clean.empty:
            return round(smi_clean.iloc[-1], 2)
        
        return None
    
    except Exception as e:
        print(f" Error SMI 4h: {e}")
        return None

def obtener_smi_semanal(ticker):
    """Obtiene SMI semanal"""
    try:
        stock = yf.Ticker(ticker)
        datos = stock.history(period="1y", interval="1wk")
        
        if datos.empty or len(datos) < 5:
            return None
        
        smi_temp = calcular_smi_rapido(datos['High'], datos['Low'], datos['Close'])
        smi_clean = smi_temp.dropna()
        
        if not smi_clean.empty:
            return round(smi_clean.iloc[-1], 2)
        
        return None
    
    except Exception as e:
        print(f" Error SMI semanal: {e}")
        return None

def detectar_pinchos(ticker):
    """Detecta pinchos alcistas y bajistas"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="90d", interval="1d")
        
        if hist.empty or len(hist) < 10:
            return [], []
        
        UMBRAL = 0.05
        
        pinchos_alcistas = []
        pinchos_bajistas = []
        
        for idx, row in hist.iterrows():
            minimo = row['Low']
            maximo = row['High']
            cierre = row['Close']
            fecha = idx.strftime('%d/%m/%Y')
            
            recuperacion = (cierre - minimo) / minimo
            if recuperacion > UMBRAL:
                pinchos_alcistas.append(f"{fecha}: giró en {round(minimo,2)}€ (recuperó {round(recuperacion*100,1)}%)")
            
            caida = (maximo - cierre) / cierre
            if caida > UMBRAL:
                pinchos_bajistas.append(f"{fecha}: giró en {round(maximo,2)}€ (cayó {round(caida*100,1)}%)")
        
        return pinchos_alcistas[:3], pinchos_bajistas[:3]
    
    except Exception as e:
        print(f" Error detectando pinchos: {e}")
        return [], []

def detectar_gaps(ticker):
    """Detecta gaps REALES"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="90d", interval="1d")
        
        if hist.empty or len(hist) < 5:
            return [], []
        
        UMBRAL_PORCENTAJE = 1.0
        
        gaps_alcistas = []
        gaps_bajistas = []
        
        for i in range(1, len(hist)):
            max_anterior = hist.iloc[i-1]['High']
            min_anterior = hist.iloc[i-1]['Low']
            min_actual = hist.iloc[i]['Low']
            max_actual = hist.iloc[i]['High']
            fecha_actual = hist.index[i].strftime('%d/%m/%Y')
            
            if min_actual > max_anterior:
                diferencia = min_actual - max_anterior
                porcentaje = (diferencia / max_anterior) * 100
                
                if porcentaje >= UMBRAL_PORCENTAJE:
                    estado = "ABIERTO"
                    for j in range(i+1, len(hist)):
                        if hist.iloc[j]['Low'] <= max_anterior:
                            estado = "CERRADO"
                            break
                    gaps_alcistas.append(f"{fecha_actual}: {round(max_anterior,2)}€ → {round(min_actual,2)}€ ({round(porcentaje,1)}%) - {estado}")
            
            elif max_actual < min_anterior:
                diferencia = min_anterior - max_actual
                porcentaje = (diferencia / min_anterior) * 100
                
                if porcentaje >= UMBRAL_PORCENTAJE:
                    estado = "ABIERTO"
                    for j in range(i+1, len(hist)):
                        if hist.iloc[j]['High'] >= min_anterior:
                            estado = "CERRADO"
                            break
                    gaps_bajistas.append(f"{fecha_actual}: {round(min_anterior,2)}€ → {round(max_actual,2)}€ ({round(porcentaje,1)}%) - {estado}")
        
        return gaps_alcistas[:3], gaps_bajistas[:3]
    
    except Exception as e:
        print(f" Error detectando gaps: {e}")
        return [], []

def identificar_niveles(ticker, precio_actual):
    """Identifica SOPORTES y RESISTENCIAS"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="90d", interval="1d")
        
        if hist.empty or len(hist) < 20:
            return [], []
        
        TOLERANCIA = 0.006
        
        todos_los_precios = []
        for i in range(len(hist)):
            todos_los_precios.append(round(hist.iloc[i]['Low'], 3))
            todos_los_precios.append(round(hist.iloc[i]['High'], 3))
        
        def agrupar_por_zona(precios):
            grupos = []
            usado = [False] * len(precios)
            
            for i in range(len(precios)):
                if usado[i]:
                    continue
                
                grupo = [precios[i]]
                usado[i] = True
                
                for j in range(len(precios)):
                    if not usado[j]:
                        for precio_grupo in grupo:
                            if abs(precios[j] - precio_grupo) / precio_grupo < TOLERANCIA:
                                grupo.append(precios[j])
                                usado[j] = True
                                break
                
                if len(grupo) >= 2:
                    grupos.append({
                        "minimo": min(grupo),
                        "maximo": max(grupo),
                        "toques": len(grupo)
                    })
            
            grupos.sort(key=lambda x: x["toques"], reverse=True)
            return grupos
        
        todos_los_grupos = agrupar_por_zona(todos_los_precios)
        
        soportes = []
        resistencias = []
        
        for g in todos_los_grupos:
            if g["maximo"] < precio_actual:
                soportes.append(f"{g['minimo']}-{g['maximo']}€ ({g['toques']} toques)")
            elif g["minimo"] > precio_actual:
                resistencias.append(f"{g['minimo']}-{g['maximo']}€ ({g['toques']} toques)")
        
        return soportes[:3], resistencias[:3]
    
    except Exception as e:
        print(f" Error identificando niveles: {e}")
        return [], []

def evaluar_caso(smi_4h, smi_diario, giro_positivo):
    """
    Evalúa los 7 casos:
    - Casos 1-5: Requieren SMI 4h en sobreventa (< -40)
    - Casos 6-7: Solo miran SMI diario (independientes del 4h)
    """
    SOBREVENTA = -40
    SOBRECOMPRA = 40
    
    # ============================================
    # NUEVAS SEÑALES SOLO CON DIARIO (CASOS 6 y 7)
    # NO requieren SMI 4h
    # ============================================
    if smi_diario is not None and smi_diario < SOBREVENTA:
        if giro_positivo:
            return 6, "🟣 COMPRA INMEDIATA (señal directa por diario)", False
        else:
            return 7, "🟠 A PUNTO DE COMPRA (vigilar evolución diaria)", False
    
    # ============================================
    # SEÑALES CON GATILLO (requieren SMI 4h < -40)
    # ============================================
    if smi_4h is None or smi_4h >= SOBREVENTA:
        return None, "SMI 4h NO en sobreventa - SE IGNORA", False
    
    # Caso 1
    if smi_diario is not None and smi_diario < SOBREVENTA and giro_positivo:
        return 1, "🔴 COMPRA YA (diario sobreventa + pendiente positiva)", True
    
    # Caso 2
    if smi_diario is not None and smi_diario < SOBREVENTA and not giro_positivo:
        return 2, "🟡 COMPRA CON RIESGO (diario sobreventa + pendiente negativa)", True
    
    # Caso 3
    if smi_diario is not None and -40 <= smi_diario <= 40 and not giro_positivo:
        return 3, "🔵 REBOTE CORTO (tendencia bajista, solo rebote)", True
    
    # Caso 4
    if smi_diario is not None and -40 <= smi_diario <= 40 and giro_positivo:
        return 4, "🟢 SUBIDA (ojo resistencias)", True
    
    # Caso 5
    if smi_diario is not None and smi_diario > SOBRECOMPRA:
        return 5, "⚡ ÚLTIMA SUBIDA (antes de vender)", True
    
    return None, "Sin caso definido", False

def guardar_recomendacion(ticker, nombre, precio, smi_4h, smi_diario, smi_semanal, 
                          caso, mensaje, pendiente_diaria, soportes, resistencias,
                          gaps_alcistas, gaps_bajistas, pinchos_alcistas, pinchos_bajistas,
                          activada_por_4h):
    """Guarda la recomendación en Supabase con todos los datos"""
    try:
        # Usar hora de España (Madrid)
        madrid_tz = pytz.timezone('Europe/Madrid')
        fecha_actual = datetime.now(madrid_tz).isoformat()
        
        # Determinar el tipo de señal
        if caso in [1,2,3,4,5]:
            tipo_señal = "GATILLO 4h"
        elif caso in [6,7]:
            tipo_señal = "DIRECTA DIARIO"
        else:
            tipo_señal = "SIN SEÑAL"
        
        data = {
            "fecha": fecha_actual,
            "ticker": ticker,
            "nombre_empresa": nombre,
            "precio_cierre": precio,
            "smi_4h": smi_4h if smi_4h else None,
            "smi_diario": smi_diario,
            "smi_semanal": smi_semanal if smi_semanal else None,
            "pendiente_diaria": pendiente_diaria,
            "caso_numero": caso,
            "recomendacion": mensaje,
            "tipo_señal": tipo_señal,
            "activada_por_4h": activada_por_4h,
            "soportes": "\n".join(soportes) if soportes else None,
            "resistencias": "\n".join(resistencias) if resistencias else None,
            "gaps_alcistas": "\n".join(gaps_alcistas) if gaps_alcistas else None,
            "gaps_bajistas": "\n".join(gaps_bajistas) if gaps_bajistas else None,
            "pinchos_alcistas": "\n".join(pinchos_alcistas) if pinchos_alcistas else None,
            "pinchos_bajistas": "\n".join(pinchos_bajistas) if pinchos_bajistas else None
        }
        
        supabase.table("recomendaciones_ibex").insert(data).execute()
        
    except Exception as e:
        print(f" ❌ Error guardando: {e}")

def analizar_todo():
    """Analiza todas las empresas y guarda TODO en Supabase"""
    print(f"🚀 Iniciando análisis - {datetime.now(pytz.timezone('Europe/Madrid')).strftime('%Y-%m-%d %H:%M:%S')} (Hora España)")
    print("=" * 70)
    print("📊 CASOS DISPONIBLES:")
    print(" CASOS 1-5: Requieren SMI 4h < -40 (GATILLO)")
    print(" CASOS 6-7: Solo requieren SMI DIARIO < -40 (DIRECTAS)")
    print("=" * 70)
    
    for ticker, nombre in EMPRESAS:
        print(f"\n📊 Analizando: {nombre} ({ticker})")
        
        # Obtener precio actual
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            precio_actual = info.get("currentPrice", info.get("regularMarketPrice"))
            if precio_actual is None:
                print(f" ⚠️ Sin precio")
                continue
        except Exception as e:
            print(f" ⚠️ Error precio: {e}")
            continue
        
        # Obtener SMIs
        smi_diario, pendiente_diaria, giro_positivo = obtener_smi_con_pendiente(ticker, "90d", "1d")
        smi_4h = obtener_smi_4h(ticker)
        smi_semanal = obtener_smi_semanal(ticker)
        
        # Detectar todo
        pinchos_alcistas, pinchos_bajistas = detectar_pinchos(ticker)
        gaps_alcistas, gaps_bajistas = detectar_gaps(ticker)
        soportes, resistencias = identificar_niveles(ticker, precio_actual)
        
        # Evaluar caso
        caso, mensaje, activada_por_4h = evaluar_caso(smi_4h, smi_diario, giro_positivo)
        
        print(f" 💰 Precio: {precio_actual}€")
        print(f" 🕐 SMI 4h: {smi_4h}")
        print(f" 📈 SMI Diario: {smi_diario} (Pendiente: {pendiente_diaria})")
        print(f" 📊 Caso: {caso} - {mensaje}")
        print(f" 🔘 Activada por 4h: {'✅' if activada_por_4h else '❌'}")
        
        # Guardar TODO en Supabase
        guardar_recomendacion(ticker, nombre, precio_actual, smi_4h, smi_diario, 
                              smi_semanal, caso, mensaje, pendiente_diaria,
                              soportes, resistencias, gaps_alcistas, gaps_bajistas,
                              pinchos_alcistas, pinchos_bajistas, activada_por_4h)
        
        time.sleep(0.5)
    
    print("\n✅ Análisis completado")

if __name__ == "__main__":
    analizar_todo()
