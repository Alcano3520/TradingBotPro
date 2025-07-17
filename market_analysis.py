import pandas as pd
import numpy as np
import logging
from typing import Dict, Tuple

# Importar TA-Lib de forma opcional
try:
    import talib
    TALIB_AVAILABLE = True
    logging.info("✅ TA-Lib disponible - Usando implementación optimizada")
except ImportError:
    TALIB_AVAILABLE = False
    logging.info("⚠️ TA-Lib no disponible - Usando implementación manual (funciona igual)")

class SimpleMarketAnalyzer:
    """
    Analizador de mercado implementando la estrategia MOMENTUM + REVERSIÓN ADAPTATIVA
    Exactamente como especifica la guía
    Funciona CON o SIN TA-Lib instalado
    """
    
    def __init__(self):
        self.indicators = {}
        
        # Parámetros de la estrategia (desde la guía)
        self.RSI_BUY_MIN = 30
        self.RSI_BUY_MAX = 60
        self.RSI_SELL = 75
        self.MIN_VOLUME_RATIO = 1.5
        self.SMA_PERIOD = 20
        
        logging.info(f"📊 Analizador inicializado - TA-Lib: {'Disponible' if TALIB_AVAILABLE else 'Manual'}")
    
    def analyze_pair(self, df: pd.DataFrame) -> Dict:
        """
        Analizar un par y devolver señal según estrategia de la guía
        
        SEÑAL DE COMPRA (4 CONDICIONES OBLIGATORIAS):
        1. RSI entre 30-60: No sobrecomprado, con momentum
        2. Precio > SMA 20: Tendencia alcista a corto plazo  
        3. Volumen > 1.5x promedio: Confirmación con volumen
        4. MACD > 0: Momentum positivo confirmado
        
        SEÑAL DE VENTA (CUALQUIERA):
        1. RSI > 75: Sobrecompra peligrosa
        2. Otros criterios manejados en trading_engine
        """
        try:
            if len(df) < 50:
                return {'signal': 'WAIT', 'reason': 'Datos insuficientes', 'confidence': 0}

            # ============ CALCULAR INDICADORES ============
            
            # RSI (14 períodos)
            rsi = self.calculate_rsi(df['close'])
            
            # SMA 20
            sma_20 = df['close'].rolling(20).mean()
            
            # Volumen promedio (20 períodos)
            volume_avg = df['volume'].rolling(20).mean()
            
            # MACD (12, 26, 9)
            macd_line, macd_signal, macd_hist = self.calculate_macd(df['close'])
            
            # ============ OBTENER VALORES ACTUALES ============
            
            current_price = float(df['close'].iloc[-1])
            current_rsi = float(rsi.iloc[-1])
            current_sma = float(sma_20.iloc[-1])
            current_volume = float(df['volume'].iloc[-1])
            avg_volume = float(volume_avg.iloc[-1])
            current_macd = float(macd_line.iloc[-1])
            
            # Calcular ratio de volumen
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
            
            # ============ DATOS DE LA SEÑAL ============
            
            signal_data = {
                'price': current_price,
                'rsi': current_rsi,
                'sma_20': current_sma,
                'volume_ratio': volume_ratio,
                'macd': current_macd,
                'macd_signal': float(macd_signal.iloc[-1]),
                'volume': current_volume,
                'avg_volume': avg_volume
            }
            
            # ============ LÓGICA DE SEÑALES ============
            
            # SEÑAL DE VENTA PRIORITARIA (RSI Sobrecompra)
            if current_rsi > self.RSI_SELL:
                return {
                    'signal': 'SELL',
                    'confidence': 0.9,
                    'data': signal_data,
                    'reason': f'RSI sobrecomprado ({current_rsi:.1f} > {self.RSI_SELL})'
                }
            
            # SEÑAL DE COMPRA (4 CONDICIONES OBLIGATORIAS)
            buy_conditions = []
            buy_reasons = []
            
            # Condición 1: RSI entre 30-60
            rsi_ok = self.RSI_BUY_MIN <= current_rsi <= self.RSI_BUY_MAX
            buy_conditions.append(rsi_ok)
            if rsi_ok:
                buy_reasons.append(f"RSI óptimo ({current_rsi:.1f})")
            else:
                buy_reasons.append(f"RSI fuera de rango ({current_rsi:.1f})")
            
            # Condición 2: Precio > SMA 20
            price_above_sma = current_price > current_sma
            buy_conditions.append(price_above_sma)
            if price_above_sma:
                pct_above = ((current_price - current_sma) / current_sma) * 100
                buy_reasons.append(f"Precio sobre SMA20 (+{pct_above:.2f}%)")
            else:
                pct_below = ((current_sma - current_price) / current_sma) * 100
                buy_reasons.append(f"Precio bajo SMA20 (-{pct_below:.2f}%)")
            
            # Condición 3: Volumen > 1.5x promedio
            volume_ok = volume_ratio > self.MIN_VOLUME_RATIO
            buy_conditions.append(volume_ok)
            if volume_ok:
                buy_reasons.append(f"Alto volumen ({volume_ratio:.2f}x)")
            else:
                buy_reasons.append(f"Volumen bajo ({volume_ratio:.2f}x)")
            
            # Condición 4: MACD > 0
            macd_ok = current_macd > 0
            buy_conditions.append(macd_ok)
            if macd_ok:
                buy_reasons.append(f"MACD positivo ({current_macd:.6f})")
            else:
                buy_reasons.append(f"MACD negativo ({current_macd:.6f})")
            
            # ============ DETERMINAR SEÑAL FINAL ============
            
            # Si todas las condiciones de compra se cumplen
            if all(buy_conditions):
                confidence = self.calculate_confidence(signal_data, buy_conditions)
                return {
                    'signal': 'BUY',
                    'confidence': confidence,
                    'data': signal_data,
                    'reason': 'Momentum alcista confirmado: ' + ', '.join(buy_reasons),
                    'conditions_met': f"4/4 condiciones cumplidas"
                }
            
            # Si no se cumplen todas las condiciones
            conditions_met = sum(buy_conditions)
            return {
                'signal': 'WAIT',
                'confidence': 0.0,
                'data': signal_data,
                'reason': f'Condiciones incompletas ({conditions_met}/4): ' + ', '.join(buy_reasons),
                'conditions_met': f"{conditions_met}/4 condiciones cumplidas"
            }
            
        except Exception as e:
            logging.error(f"❌ Error analizando par: {e}")
            return {'signal': 'ERROR', 'reason': str(e), 'confidence': 0}
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calcular RSI - Funciona con o sin TA-Lib"""
        try:
            if TALIB_AVAILABLE:
                # Usar TA-Lib (más rápido y preciso)
                rsi_values = talib.RSI(prices.values, timeperiod=period)
                return pd.Series(rsi_values, index=prices.index)
            else:
                # Implementación manual (igualmente efectiva)
                delta = prices.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
                
                # Evitar división por cero
                rs = gain / loss.replace(0, np.nan)
                rsi = 100 - (100 / (1 + rs))
                
                return rsi.fillna(50)  # Valor neutral para NaN
                
        except Exception as e:
            logging.error(f"❌ Error calculando RSI: {e}")
            # Retornar serie con valores neutros
            return pd.Series([50] * len(prices), index=prices.index)
    
    def calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calcular MACD - Funciona con o sin TA-Lib"""
        try:
            if TALIB_AVAILABLE:
                # Usar TA-Lib (más rápido)
                macd_line, macd_signal, macd_hist = talib.MACD(
                    prices.values, fastperiod=fast, slowperiod=slow, signalperiod=signal
                )
                return (
                    pd.Series(macd_line, index=prices.index),
                    pd.Series(macd_signal, index=prices.index),
                    pd.Series(macd_hist, index=prices.index)
                )
            else:
                # Implementación manual (igualmente efectiva)
                ema_fast = prices.ewm(span=fast, adjust=False).mean()
                ema_slow = prices.ewm(span=slow, adjust=False).mean()
                macd_line = ema_fast - ema_slow
                macd_signal = macd_line.ewm(span=signal, adjust=False).mean()
                macd_hist = macd_line - macd_signal
                
                return macd_line, macd_signal, macd_hist
                
        except Exception as e:
            logging.error(f"❌ Error calculando MACD: {e}")
            # Retornar series con valores neutros
            zeros = pd.Series([0] * len(prices), index=prices.index)
            return zeros, zeros, zeros
    
    def calculate_confidence(self, data: Dict, conditions: list) -> float:
        """
        Calcular confianza de la señal basada en la fuerza de los indicadores
        Rango: 0.6 a 1.0 (solo señales de alta calidad)
        """
        confidence = 0.6  # Base mínima para señales válidas
        
        try:
            # Bonus por RSI en zona óptima (40-55 es ideal)
            rsi = data['rsi']
            if 40 <= rsi <= 55:
                confidence += 0.15
            elif 35 <= rsi <= 40 or 55 <= rsi <= 60:
                confidence += 0.10
            
            # Bonus por volumen excepcional
            volume_ratio = data['volume_ratio']
            if volume_ratio > 3.0:
                confidence += 0.15
            elif volume_ratio > 2.0:
                confidence += 0.10
            elif volume_ratio > 1.8:
                confidence += 0.05
            
            # Bonus por MACD fuerte
            macd = data['macd']
            if macd > 0.001:  # MACD muy positivo
                confidence += 0.10
            elif macd > 0:
                confidence += 0.05
            
            # Bonus por precio bien sobre SMA
            price_above_sma_pct = (data['price'] - data['sma_20']) / data['sma_20']
            if price_above_sma_pct > 0.02:  # 2% sobre SMA
                confidence += 0.10
            elif price_above_sma_pct > 0.01:  # 1% sobre SMA
                confidence += 0.05
            
        except Exception as e:
            logging.error(f"❌ Error calculando confianza: {e}")
        
        # Limitar confianza máxima
        return min(confidence, 1.0)
    
    def get_market_conditions(self, df: pd.DataFrame) -> Dict:
        """Obtener condiciones generales del mercado"""
        try:
            # Calcular volatilidad (ATR normalizado)
            high_low = df['high'] - df['low']
            high_close = abs(df['high'] - df['close'].shift())
            low_close = abs(df['low'] - df['close'].shift())
            
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = true_range.rolling(14).mean()
            volatility = (atr.iloc[-1] / df['close'].iloc[-1]) * 100
            
            # Calcular tendencia general (SMA 50 vs SMA 200)
            sma_50 = df['close'].rolling(50).mean()
            sma_200 = df['close'].rolling(200).mean() if len(df) >= 200 else sma_50
            
            trend = "ALCISTA" if sma_50.iloc[-1] > sma_200.iloc[-1] else "BAJISTA"
            
            # Calcular momentum del precio (cambio en 10 períodos)
            price_momentum = ((df['close'].iloc[-1] - df['close'].iloc[-11]) / df['close'].iloc[-11]) * 100
            
            return {
                'volatility': volatility,
                'trend': trend,
                'momentum': price_momentum,
                'market_strength': self._assess_market_strength(df)
            }
            
        except Exception as e:
            logging.error(f"❌ Error calculando condiciones de mercado: {e}")
            return {
                'volatility': 2.0,
                'trend': 'NEUTRAL',
                'momentum': 0.0,
                'market_strength': 'MEDIO'
            }
    
    def _assess_market_strength(self, df: pd.DataFrame) -> str:
        """Evaluar la fuerza del mercado"""
        try:
            # Calcular varios indicadores de fuerza
            rsi = self.calculate_rsi(df['close']).iloc[-1]
            
            # Volumen relativo
            vol_ratio = df['volume'].iloc[-1] / df['volume'].rolling(20).mean().iloc[-1]
            
            # Precio relativo a SMA
            price_vs_sma = df['close'].iloc[-1] / df['close'].rolling(20).mean().iloc[-1]
            
            # Evaluar fuerza
            strength_score = 0
            
            if 40 <= rsi <= 60:
                strength_score += 1
            if vol_ratio > 1.2:
                strength_score += 1
            if price_vs_sma > 1.01:
                strength_score += 1
                
            if strength_score >= 2:
                return "FUERTE"
            elif strength_score >= 1:
                return "MEDIO"
            else:
                return "DÉBIL"
                
        except:
            return "MEDIO"