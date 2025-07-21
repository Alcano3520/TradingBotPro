import ccxt
import time
import logging
import json
import os
import requests
from typing import Dict, List, Tuple, Optional
import pandas as pd
from decimal import Decimal, ROUND_DOWN
from datetime import datetime

class BinanceConnection:
    """Conexión robusta con Binance - SOLUCIÓN DEFINITIVA TIMESTAMP"""
    
    def __init__(self):
        self.exchange = None
        self.is_connected = False
        self.last_error = None
        self.rate_limit_delay = 0.1
        
    def connect(self, api_key: str, api_secret: str, testnet: bool = False) -> bool:
        """Conectar con Binance usando método robusto del timestamp"""
        try:
            logging.info("🔄 Iniciando conexión robusta con Binance...")
            
            # MÉTODO 1: Configuración básica inicial
            self.exchange = ccxt.binance({
                'apiKey': api_key,
                'secret': api_secret,
                'sandbox': testnet,
                'enableRateLimit': True,
                'rateLimit': 1200,  # Más conservador: 1.2 segundos
                'timeout': 30000,
                'options': {
                    'defaultType': 'spot',
                    'adjustForTimeDifference': True,
                    'recvWindow': 60000,  # 60 segundos de ventana
                }
            })
            
            # MÉTODO 2: Sincronización manual robusta
            logging.info("🕐 Sincronizando tiempo con servidor Binance...")
            
            # Obtener tiempo del servidor usando endpoint directo
            try:
                response = requests.get('https://api.binance.com/api/v3/time', timeout=10)
                if response.status_code == 200:
                    server_data = response.json()
                    server_time = int(server_data['serverTime'])
                    local_time = int(time.time() * 1000)
                    time_offset = server_time - local_time
                    
                    logging.info(f"⏰ Servidor: {server_time}, Local: {local_time}")
                    logging.info(f"⚡ Offset calculado: {time_offset}ms")
                    
                    # Aplicar offset con margen de seguridad
                    safety_margin = 2000  # 2 segundos extra
                    final_offset = time_offset + safety_margin
                    
                    self.exchange.options['timeDifference'] = final_offset
                    logging.info(f"✅ Offset final aplicado: {final_offset}ms")
                    
                else:
                    logging.warning("⚠️ No se pudo obtener tiempo del servidor")
                    # Usar offset predeterminado conservador
                    self.exchange.options['timeDifference'] = 5000  # 5 segundos
                    
            except Exception as time_error:
                logging.warning(f"⚠️ Error sincronizando tiempo: {time_error}")
                # Usar offset predeterminado muy conservador
                self.exchange.options['timeDifference'] = 10000  # 10 segundos
            
            # MÉTODO 3: Verificación con múltiples intentos
            logging.info("🧪 Verificando conexión...")
            
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    logging.info(f"🔄 Intento de conexión {attempt + 1}/{max_attempts}")
                    
                    # Esperar antes de cada intento
                    if attempt > 0:
                        wait_time = 3 * attempt
                        logging.info(f"⏳ Esperando {wait_time} segundos...")
                        time.sleep(wait_time)
                    
                    # Test 1: Ping básico
                    logging.info("📡 Probando ping...")
                    ping_result = self.exchange.public_get_ping()
                    logging.info("✅ Ping exitoso")
                    
                    # Test 2: Obtener información de cuenta
                    logging.info("🔐 Verificando credenciales...")
                    account_info = self.exchange.private_get_account()
                    logging.info("✅ Credenciales válidas")
                    
                    # Test 3: Verificar permisos
                    if not account_info.get('canTrade', False):
                        self.last_error = "❌ API Key no tiene permisos de trading"
                        logging.error(self.last_error)
                        return False
                    
                    logging.info("✅ Permisos de trading confirmados")
                    
                    # Test 4: Obtener balance
                    logging.info("💰 Obteniendo balance...")
                    balance = self.exchange.fetch_balance()
                    usdt_balance = balance.get('USDT', {}).get('free', 0)
                    
                    # ¡CONEXIÓN EXITOSA!
                    self.is_connected = True
                    
                    logging.info("🎉 ¡CONEXIÓN EXITOSA!")
                    logging.info(f"📊 Modo: {'⚠️ TESTNET' if testnet else '💰 PRODUCCIÓN - DINERO REAL'}")
                    logging.info(f"💵 Balance USDT: {usdt_balance:.2f}")
                    logging.info(f"🚀 Bot listo para generar ganancias!")
                    
                    return True
                    
                except ccxt.BaseError as e:
                    error_msg = str(e)
                    logging.warning(f"⚠️ Intento {attempt + 1} falló: {error_msg}")
                    
                    if "timestamp" in error_msg.lower() or "-1021" in error_msg:
                        # Error de timestamp - aumentar offset
                        current_offset = self.exchange.options.get('timeDifference', 0)
                        new_offset = current_offset + 5000  # Añadir 5 segundos más
                        self.exchange.options['timeDifference'] = new_offset
                        logging.info(f"🔧 Aumentando offset a: {new_offset}ms")
                        
                    elif "permission" in error_msg.lower() or "-2015" in error_msg:
                        self.last_error = "❌ API Key inválida o sin permisos"
                        logging.error(self.last_error)
                        return False
                        
                    if attempt == max_attempts - 1:
                        self.last_error = f"❌ Conexión fallida: {error_msg}"
                        logging.error(self.last_error)
                        return False
            
            return False
            
        except Exception as e:
            self.last_error = f"❌ Error crítico: {str(e)}"
            logging.error(self.last_error)
            return False
    
    def get_balance(self) -> Dict[str, float]:
            """Obtener balance actual INCLUYENDO TODAS LAS CRIPTOMONEDAS"""
            try:
                if not self.is_connected or not self.exchange:
                    return {}
                    
                time.sleep(self.rate_limit_delay)
                balance = self.exchange.fetch_balance()
                
                # Balance USDT disponible para trading
                usdt_free = balance.get('USDT', {}).get('free', 0)
                usdt_total = balance.get('USDT', {}).get('total', 0)
                
                # Calcular valor total de TODAS las criptomonedas
                total_value_usdt = 0
                
                for symbol, bal in balance.items():
                    if isinstance(bal, dict) and bal.get('total', 0) > 0:
                        total_amount = bal.get('total', 0)
                        
                        if symbol == 'USDT':
                            total_value_usdt += total_amount
                        else:
                            try:
                                # Obtener precio en USDT
                                ticker = self.exchange.fetch_ticker(f"{symbol}USDT")
                                price_usdt = float(ticker['last'])
                                value_usdt = total_amount * price_usdt
                                total_value_usdt += value_usdt
                                
                                logging.info(f"💰 {symbol}: {total_amount:.6f} = ${value_usdt:.2f}")
                            except:
                                pass  # Si no se puede obtener precio, ignorar
                
                logging.info(f"💰 BALANCE TOTAL: ${total_value_usdt:.2f} (USDT libre: ${usdt_free:.2f})")
                
                return {
                    'USDT': usdt_free,                    # USDT libre para trading
                    'total_usdt': usdt_total,             # USDT total
                    'total_value_usdt': total_value_usdt  # VALOR TOTAL DE TODO
                }
                
            except Exception as e:
                logging.error(f"❌ Error obteniendo balance: {e}")
                return {}    
    
    def get_all_positions(self) -> Dict:
            """Obtener TODAS las posiciones de criptomonedas en la cuenta"""
            try:
                if not self.is_connected or not self.exchange:
                    return {}
                    
                time.sleep(self.rate_limit_delay)
                balance = self.exchange.fetch_balance()
                
                positions = {}
                
                for symbol, bal in balance.items():
                    if isinstance(bal, dict) and bal.get('total', 0) > 0:
                        total_amount = bal.get('total', 0)
                        free_amount = bal.get('free', 0)
                        
                        # Ignorar USDT ya que es nuestra moneda base
                        if symbol == 'USDT':
                            continue
                        
                        # Solo incluir si hay cantidad significativa
                        if total_amount < 0.000001:  # Muy pequeño, ignorar
                            continue
                            
                        try:
                            # Obtener precio actual
                            ticker_symbol = f"{symbol}USDT"
                            ticker = self.exchange.fetch_ticker(ticker_symbol)
                            current_price = float(ticker['last'])
                            current_value = total_amount * current_price
                            
                            # Solo incluir si vale más de $0.10
                            if current_value < 0.10:
                                continue
                            
                            positions[symbol] = {
                                'symbol': symbol,
                                'quantity': total_amount,
                                'free': free_amount,
                                'current_price': current_price,
                                'current_value': current_value,
                                'entry_price': current_price,  # No sabemos el precio de entrada real
                                'entry_time': datetime.now(),  # Timestamp actual
                                'source': 'existing'  # Marcar como posición existente
                            }
                            
                            logging.info(f"📦 Posición detectada: {symbol} = {total_amount:.6f} = ${current_value:.2f}")
                            
                        except Exception as e:
                            logging.warning(f"⚠️ No se pudo obtener precio de {symbol}: {e}")
                
                logging.info(f"📊 Total posiciones detectadas: {len(positions)}")
                return positions
                
            except Exception as e:
                logging.error(f"❌ Error obteniendo posiciones: {e}")
                return {}
    def get_price(self, symbol: str) -> float:
        try:
            if not self.is_connected or not self.exchange:
                return 0.0
                
            time.sleep(self.rate_limit_delay)
            ticker = self.exchange.fetch_ticker(symbol)
            return float(ticker['last'])
            
        except ccxt.NetworkError as e:
            logging.warning(f"⚠️ Network error {symbol}: {e}")
            return 0.0
        except ccxt.RequestTimeout as e:
            logging.warning(f"⚠️ Timeout {symbol}: {e}")
            return 0.0
        except Exception as e:
            logging.error(f"❌ Error obteniendo precio {symbol}: {e}")
            return 0.0      
    
    def get_klines(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        """Obtener datos históricos"""
        try:
            if not self.is_connected or not self.exchange:
                return pd.DataFrame()
                
            time.sleep(self.rate_limit_delay)
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            if not ohlcv or len(ohlcv) < 50:
                return pd.DataFrame()
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.dropna()
            df = df[df['volume'] > 0]
            
            return df
            
        except Exception as e:
            logging.error(f"❌ Error obteniendo klines {symbol}: {e}")
            return pd.DataFrame()
    
    def place_market_buy(self, symbol: str, usdt_amount: float) -> Dict:
        """Ejecutar compra a mercado"""
        try:
            if not self.is_connected or not self.exchange:
                return {'success': False, 'error': 'No conectado'}
            
            price = self.get_price(symbol)
            if price <= 0:
                return {'success': False, 'error': 'No se pudo obtener precio'}
            
            quantity = usdt_amount / price
            market = self.exchange.market(symbol)
            min_amount = market.get('limits', {}).get('amount', {}).get('min', 0)
            
            if quantity < min_amount:
                return {'success': False, 'error': f'Cantidad mínima: {min_amount}'}
            
            quantity = self.exchange.amount_to_precision(symbol, quantity)
            
            time.sleep(self.rate_limit_delay)
            order = self.exchange.create_market_buy_order(symbol, float(quantity))
            
            if order['status'] == 'closed' or order['filled'] > 0:
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
                
        except Exception as e:
            logging.error(f"❌ Error ejecutando compra {symbol}: {e}")
            return {'success': False, 'error': str(e)}
    
    def place_market_sell(self, symbol: str, quantity: float) -> Dict:
        """Ejecutar venta a mercado"""
        try:
            if not self.is_connected or not self.exchange:
                return {'success': False, 'error': 'No conectado'}
            
            market = self.exchange.market(symbol)
            quantity = self.exchange.amount_to_precision(symbol, quantity)
            
            time.sleep(self.rate_limit_delay)
            order = self.exchange.create_market_sell_order(symbol, float(quantity))
            
            if order['status'] == 'closed' or order['filled'] > 0:
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