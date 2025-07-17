import ccxt
import time
import logging
import json
import os
import requests
from typing import Dict, List, Tuple, Optional
import pandas as pd
from decimal import Decimal, ROUND_DOWN

class BinanceConnection:
    """Conexión robusta y optimizada con Binance - SOLUCIONA ERRORES DE TIMESTAMP"""
    
    def __init__(self):
        self.exchange = None
        self.is_connected = False
        self.last_error = None
        self.rate_limit_delay = 0.1
        self.time_offset = 0  # Offset para sincronizar tiempo
        
    def sync_time_with_binance(self):
        """Sincronizar tiempo con el servidor de Binance"""
        try:
            # Obtener tiempo del servidor de Binance
            response = requests.get('https://api.binance.com/api/v3/time', timeout=10)
            server_time = response.json()['serverTime']
            
            # Calcular offset
            local_time = int(time.time() * 1000)
            self.time_offset = server_time - local_time
            
            logging.info(f"🕐 Tiempo sincronizado - Offset: {self.time_offset}ms")
            return True
            
        except Exception as e:
            logging.warning(f"⚠️ No se pudo sincronizar tiempo: {e}")
            self.time_offset = 0
            return False
    
    def connect(self, api_key: str, api_secret: str, testnet: bool = False) -> bool:
        """Conectar con Binance de forma robusta - SOLUCIÓN DEFINITIVA TIMESTAMP"""
        try:
            logging.info("🔄 Iniciando conexión con Binance...")
            
            # PASO 1: Configurar exchange básico
            self.exchange = ccxt.binance({
                'apiKey': api_key,
                'secret': api_secret,
                'sandbox': testnet,
                'enableRateLimit': True,
                'rateLimit': 200,  # Más conservador
                'timeout': 30000,
                'options': {
                    'defaultType': 'spot',
                    'adjustForTimeDifference': True,
                    'recvWindow': 60000,  # Ventana muy amplia: 60 segundos
                }
            })
            
            # PASO 2: Forzar sincronización de tiempo
            logging.info("🕐 Sincronizando tiempo con Binance...")
            try:
                # Obtener tiempo del servidor
                server_time_response = self.exchange.public_get_time()
                server_time = server_time_response['serverTime']
                
                # Tiempo local
                local_time = int(time.time() * 1000)
                
                # Calcular diferencia
                time_diff = server_time - local_time
                
                logging.info(f"⏰ Diferencia de tiempo: {time_diff}ms")
                
                # Aplicar corrección
                self.exchange.options['timeDifference'] = time_diff
                
                # Esperar un momento para estabilizar
                time.sleep(1)
                
            except Exception as sync_error:
                logging.warning(f"⚠️ No se pudo sincronizar tiempo automáticamente: {sync_error}")
            
            # PASO 3: Verificar conexión con múltiples intentos
            logging.info("🧪 Verificando conexión...")
            
            max_attempts = 5
            for attempt in range(max_attempts):
                try:
                    logging.info(f"🔄 Intento {attempt + 1}/{max_attempts}")
                    
                    # Test básico
                    ping_result = self.exchange.public_get_ping()
                    logging.info("✅ Ping exitoso")
                    
                    # Verificar cuenta
                    account_info = self.exchange.private_get_account()
                    logging.info("✅ Información de cuenta obtenida")
                    
                    if not account_info.get('canTrade', False):
                        raise Exception("❌ API Key no tiene permisos de trading")
                    
                    # Test de balance
                    balance = self.exchange.fetch_balance()
                    logging.info("✅ Balance obtenido")
                    
                    # Si llegamos aquí, la conexión es exitosa
                    self.is_connected = True
                    
                    usdt_balance = balance.get('USDT', {}).get('free', 0)
                    logging.info(f"✅ CONEXIÓN EXITOSA")
                    logging.info(f"📊 Modo: {'Testnet' if testnet else '🔴 PRODUCCIÓN - DINERO REAL'}")
                    logging.info(f"💰 Balance USDT disponible: {usdt_balance:.2f}")
                    logging.info(f"🎯 Listo para generar ganancias!")
                    
                    return True
                    
                except ccxt.BaseError as e:
                    error_msg = str(e)
                    logging.warning(f"⚠️ Intento {attempt + 1} falló: {error_msg}")
                    
                    if "timestamp" in error_msg.lower() or "-1021" in error_msg:
                        # Error de timestamp, ajustar tiempo
                        if attempt < max_attempts - 1:
                            logging.info("🔧 Ajustando sincronización de tiempo...")
                            
                            # Ajuste más agresivo
                            try:
                                # Nuevo intento de sincronización
                                response = requests.get('https://api.binance.com/api/v3/time', timeout=5)
                                if response.status_code == 200:
                                    server_time = response.json()['serverTime']
                                    local_time = int(time.time() * 1000)
                                    new_diff = server_time - local_time
                                    
                                    # Aplicar con margen de seguridad
                                    self.exchange.options['timeDifference'] = new_diff + 1000  # +1 segundo extra
                                    
                                    logging.info(f"⚡ Nueva diferencia aplicada: {new_diff + 1000}ms")
                                    
                                    time.sleep(2)
                                    continue
                            except:
                                pass
                    
                    elif "permission" in error_msg.lower() or "-2015" in error_msg:
                        self.last_error = "❌ API Key inválida o sin permisos. Verifique sus credenciales."
                        logging.error(self.last_error)
                        return False
                        
                    elif attempt == max_attempts - 1:
                        # Último intento fallido
                        self.last_error = f"❌ Conexión fallida después de {max_attempts} intentos: {error_msg}"
                        logging.error(self.last_error)
                        return False
                    
                    # Esperar antes del siguiente intento
                    time.sleep(2 ** attempt)  # Backoff exponencial
            
            return False
            
        except Exception as e:
            self.last_error = f"❌ Error crítico de conexión: {str(e)}"
            logging.error(self.last_error)
            return False
    
    def get_balance(self) -> Dict[str, float]:
        """Obtener balance actual con manejo de errores"""
        try:
            if not self.is_connected or not self.exchange:
                return {}
                
            time.sleep(self.rate_limit_delay)
            balance = self.exchange.fetch_balance()
            
            return {
                'USDT': balance.get('USDT', {}).get('free', 0),
                'total_usdt': balance.get('USDT', {}).get('total', 0)
            }
            
        except Exception as e:
            logging.error(f"❌ Error obteniendo balance: {e}")
            return {}
    
    def get_price(self, symbol: str) -> float:
        """Obtener precio actual de un par con retry"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if not self.is_connected or not self.exchange:
                    return 0.0
                    
                time.sleep(self.rate_limit_delay)
                ticker = self.exchange.fetch_ticker(symbol)
                return float(ticker['last'])
                
            except Exception as e:
                if attempt == max_retries - 1:
                    logging.error(f"❌ Error obteniendo precio {symbol}: {e}")
                    return 0.0
                time.sleep(1)
        return 0.0
    
    def get_klines(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        """Obtener datos históricos con validación"""
        try:
            if not self.is_connected or not self.exchange:
                return pd.DataFrame()
                
            time.sleep(self.rate_limit_delay)
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            if not ohlcv or len(ohlcv) < 50:
                logging.warning(f"⚠️ Datos insuficientes para {symbol}: {len(ohlcv) if ohlcv else 0} velas")
                return pd.DataFrame()
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Validar datos
            df = df.dropna()
            df = df[df['volume'] > 0]
            
            return df
            
        except Exception as e:
            logging.error(f"❌ Error obteniendo klines {symbol}: {e}")
            return pd.DataFrame()
    
    def place_market_buy(self, symbol: str, usdt_amount: float) -> Dict:
        """Ejecutar compra a mercado con validaciones"""
        try:
            if not self.is_connected or not self.exchange:
                return {'success': False, 'error': 'No conectado'}
            
            # Obtener precio actual
            price = self.get_price(symbol)
            if price <= 0:
                return {'success': False, 'error': 'No se pudo obtener precio'}
            
            # Calcular cantidad
            quantity = usdt_amount / price
            
            # Obtener info del mercado para ajustar precision
            market = self.exchange.market(symbol)
            min_amount = market.get('limits', {}).get('amount', {}).get('min', 0)
            
            if quantity < min_amount:
                return {'success': False, 'error': f'Cantidad mínima: {min_amount}'}
            
            # Ajustar precisión
            precision = market.get('precision', {}).get('amount', 8)
            quantity = self.exchange.amount_to_precision(symbol, quantity)
            
            # Ejecutar orden
            time.sleep(self.rate_limit_delay)
            order = self.exchange.create_market_buy_order(symbol, float(quantity))
            
            # Procesar resultado
            if order['status'] == 'closed' or order['filled'] > 0:
                logging.info(f"✅ COMPRA EJECUTADA: {symbol} - {quantity} por ~${usdt_amount:.2f}")
                
                return {
                    'success': True,
                    'order_id': order['id'],
                    'symbol': symbol,
                    'quantity': float(order['filled']),
                    'price': float(order['average']) if order['average'] else price,
                    'cost': float(order['cost']),
                    'fee': float(order['fee']['cost']) if order.get('fee') else 0
                }
            else:
                return {'success': False, 'error': 'Orden no completada'}
                
        except ccxt.InsufficientFunds:
            return {'success': False, 'error': 'Fondos insuficientes'}
        except ccxt.InvalidOrder as e:
            return {'success': False, 'error': f'Orden inválida: {e}'}
        except Exception as e:
            logging.error(f"❌ Error ejecutando compra {symbol}: {e}")
            return {'success': False, 'error': str(e)}
    
    def place_market_sell(self, symbol: str, quantity: float) -> Dict:
        """Ejecutar venta a mercado con validaciones"""
        try:
            if not self.is_connected or not self.exchange:
                return {'success': False, 'error': 'No conectado'}
            
            # Ajustar precisión
            market = self.exchange.market(symbol)
            quantity = self.exchange.amount_to_precision(symbol, quantity)
            
            # Ejecutar orden
            time.sleep(self.rate_limit_delay)
            order = self.exchange.create_market_sell_order(symbol, float(quantity))
            
            # Procesar resultado
            if order['status'] == 'closed' or order['filled'] > 0:
                logging.info(f"✅ VENTA EJECUTADA: {symbol} - {quantity}")
                
                return {
                    'success': True,
                    'order_id': order['id'],
                    'symbol': symbol,
                    'quantity': float(order['filled']),
                    'price': float(order['average']) if order['average'] else 0,
                    'cost': float(order['cost']),
                    'fee': float(order['fee']['cost']) if order.get('fee') else 0
                }
            else:
                return {'success': False, 'error': 'Orden no completada'}
                
        except ccxt.InsufficientFunds:
            return {'success': False, 'error': 'Fondos insuficientes'}
        except ccxt.InvalidOrder as e:
            return {'success': False, 'error': f'Orden inválida: {e}'}
        except Exception as e:
            logging.error(f"❌ Error ejecutando venta {symbol}: {e}")
            return {'success': False, 'error': str(e)}
    
    def verify_order(self, symbol: str, order_id: str) -> Dict:
        """Verificar estado de una orden"""
        try:
            if not self.is_connected or not self.exchange:
                return {}
                
            time.sleep(self.rate_limit_delay)
            order = self.exchange.fetch_order(order_id, symbol)
            
            return {
                'status': order['status'],
                'filled': float(order['filled']),
                'remaining': float(order['remaining']),
                'cost': float(order['cost'])
            }
            
        except Exception as e:
            logging.error(f"❌ Error verificando orden {order_id}: {e}")
            return {}
    
    def get_account_info(self) -> Dict:
        """Obtener información de cuenta"""
        try:
            if not self.is_connected or not self.exchange:
                return {}
                
            time.sleep(self.rate_limit_delay)
            balance = self.exchange.fetch_balance()
            
            # Calcular estadísticas
            total_balance = sum([bal.get('total', 0) for bal in balance.values() if isinstance(bal, dict)])
            free_balance = sum([bal.get('free', 0) for bal in balance.values() if isinstance(bal, dict)])
            
            return {
                'total_balance_btc': total_balance,
                'free_balance_btc': free_balance,
                'used_balance_btc': total_balance - free_balance,
                'account_type': 'SPOT',
                'trading_enabled': True,
                'balances': balance
            }
            
        except Exception as e:
            logging.error(f"❌ Error obteniendo info de cuenta: {e}")
            return {}