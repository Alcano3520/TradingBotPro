import time
import logging
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Callable, Optional
import pandas as pd

from binance_connection import BinanceConnection
from market_analysis import SimpleMarketAnalyzer

class TradingEngine:
    """
    Motor de trading principal implementando la estrategia MOMENTUM + REVERSIÓN ADAPTATIVA
    Exactamente como especifica la guía para generar ganancias reales
    """
    
    def __init__(self, gui_callback: Optional[Callable] = None):
        """
        Inicializar el motor de trading
        
        Args:
            gui_callback: Función callback para actualizar la GUI
        """
        # Componentes principales
        self.binance = BinanceConnection()
        self.analyzer = SimpleMarketAnalyzer()
        self.gui_callback = gui_callback
        
        # Estado del bot
        self.is_running = False
        self.positions = {}  # {symbol: {quantity, entry_price, entry_time, stop_loss, take_profit}}
        self.daily_trades = 0
        self.total_fees = 0.0
        self.start_balance = 0.0
        self.last_trade_time = {}  # Para evitar trades muy frecuentes
        
        # Configuración de la estrategia (EXACTA de la guía)
        self.config = {
            'timeframe': '5m',              # 5 minutos por vela
            'take_profit': 0.03,            # 3% ganancia objetivo  
            'stop_loss': 0.015,             # 1.5% pérdida máxima
            'position_size': 0.20,          # 20% del balance por trade
            'max_positions': 3,             # Máximo 3 posiciones simultáneas
            'min_volume_ratio': 1.5,        # Volumen mínimo vs promedio
            'rsi_buy_min': 30,              # RSI mínimo para compra
            'rsi_buy_max': 60,              # RSI máximo para compra  
            'rsi_sell': 75,                 # RSI para venta por sobrecompra
            'max_hold_hours': 24,           # Máximo tiempo en posición
            'min_time_between_trades': 300, # 5 minutos entre trades del mismo par
            'min_trade_amount': 10.0        # Mínimo 10 USDT por trade
        }
        
        # Pares seleccionados (alta liquidez como especifica la guía)
        self.trading_pairs = [
            'BTCUSDT',   # Bitcoin - Mayor liquidez
            'ETHUSDT',   # Ethereum - Segunda mayor liquidez  
            'BNBUSDT',   # Binance Coin - Nativo de Binance
            'ADAUSDT',   # Cardano - Buen volumen y volatilidad
            'SOLUSDT'    # Solana - Alta volatilidad, buenos profits
        ]
        
        # Configurar logging detallado
        self.setup_logging()
        
        # Thread para el ciclo principal
        self.trading_thread = None
        self.stop_event = threading.Event()
        
        logging.info("🚀 TradingEngine inicializado con estrategia MOMENTUM + REVERSIÓN ADAPTATIVA")
    
    def setup_logging(self):
        """Configurar logging detallado para verificación"""
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        
        # Log file con fecha
        log_filename = f'trading_log_{datetime.now().strftime("%Y%m%d")}.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.FileHandler(log_filename, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        logging.info("📋 Sistema de logging configurado")
    
    def connect_exchange(self, api_key: str, api_secret: str, testnet: bool = False) -> bool:
        """Conectar con Binance y configurar balance inicial"""
        success = self.binance.connect(api_key, api_secret, testnet)
        
        if success:
            balance = self.binance.get_balance()
            self.start_balance = balance.get('total_value_usdt', balance.get('USDT', 0))
            # Reset completo de estadísticas
            self.daily_trades = 0
            self.total_fees = 0.0
            self.positions = {}
            self.last_trade_time = {}
            logging.info(f"✅ Conectado a Binance - Balance inicial: ${self.start_balance:.2f}")
            logging.info(f"📊 ANÁLISIS DE RENTABILIDAD:")
            logging.info(f"├── Take Profit: +{self.config['take_profit']*100}%")
            logging.info(f"├── Stop Loss: -{self.config['stop_loss']*100}%") 
            logging.info(f"├── Ratio Risk/Reward: 1:{self.config['take_profit']/self.config['stop_loss']:.1f}")
            logging.info(f"├── Win Rate necesario: {(self.config['stop_loss']/(self.config['take_profit']+self.config['stop_loss']))*100:.1f}%")
            logging.info(f"├── Profit esperado: 15-25% mensual")
            logging.info(f"└── Drawdown máximo: 8-12%")
            
        return success
    
    def start_trading(self):
        """Iniciar el bot de trading en thread separado"""
        if self.is_running:
            logging.warning("⚠️ El bot ya está ejecutándose")
            return
            
        self.is_running = True
        self.stop_event.clear()
        
        # Iniciar thread de trading
        self.trading_thread = threading.Thread(target=self._trading_loop, daemon=True)
        self.trading_thread.start()
        
        logging.info("🚀 TRADING BOT INICIADO")
        logging.info(f"📈 Buscando oportunidades en {len(self.trading_pairs)} pares")
    
    def stop_trading(self):
        """Detener el bot de trading"""
        if not self.is_running:
            return
            
        self.is_running = False
        self.stop_event.set()
        
        # Esperar a que termine el thread
        if self.trading_thread and self.trading_thread.is_alive():
            self.trading_thread.join(timeout=10)
            
        logging.info("⏹️ TRADING BOT DETENIDO")
    
    def _trading_loop(self):
        """Bucle principal de trading"""
        logging.info("🔄 Iniciando ciclo de trading...")
        
        while self.is_running and not self.stop_event.is_set():
            try:
                cycle_start = time.time()
                
                # 1. Verificar y gestionar posiciones existentes
                self.manage_existing_positions()
                
                # 2. Buscar nuevas oportunidades 
                self.scan_for_opportunities()
                
                # 3. Actualizar GUI si hay callback
                if self.gui_callback:
                    self.gui_callback(self.get_status_data())
                
                # 4. Esperar hasta el próximo ciclo (5 minutos)
                cycle_time = time.time() - cycle_start
                sleep_time = max(0, 300 - cycle_time)  # 300 segundos = 5 minutos
                
                logging.info(f"🔄 Ciclo completado en {cycle_time:.1f}s - Esperando {sleep_time:.1f}s")
                
                # Espera interrumpible
                if self.stop_event.wait(timeout=sleep_time):
                    break
                    
            except Exception as e:
                logging.error(f"❌ Error en ciclo de trading: {e}")
                if self.stop_event.wait(timeout=60):  # Esperar 1 minuto antes de reintentar
                    break
    
    def manage_existing_positions(self):
        """Gestionar posiciones existentes según la estrategia"""
        if not self.positions:
            return
            
        logging.info(f"📊 Gestionando {len(self.positions)} posiciones activas...")
        
        for symbol, position in list(self.positions.items()):
            try:
                current_price = self.binance.get_price(symbol)
                if current_price <= 0:
                    continue
                
                entry_price = position['entry_price']
                quantity = position['quantity']
                entry_time = position['entry_time']
                
                # Calcular P&L
                pnl_percent = (current_price - entry_price) / entry_price
                
                # Verificar condiciones de salida
                should_sell, reason = self.check_exit_conditions(
                    symbol, current_price, entry_price, entry_time, pnl_percent
                )
                
                if should_sell:
                    self.execute_sell(symbol, quantity, current_price, reason)
                
            except Exception as e:
                logging.error(f"❌ Error gestionando posición {symbol}: {e}")
    
    def check_exit_conditions(self, symbol: str, current_price: float, 
                            entry_price: float, entry_time: datetime, 
                            pnl_percent: float) -> tuple:
        """
        Verificar condiciones de salida según la estrategia de la guía
        
        SEÑALES DE VENTA (CUALQUIERA DE ESTAS):
        1. Take Profit: +3% desde entrada
        2. Stop Loss: -1.5% desde entrada  
        3. RSI > 75: Sobrecompra peligrosa
        4. Tiempo: Máximo 24 horas en posición
        """
        
        # 1. Take Profit: +3% desde entrada
        if pnl_percent >= self.config['take_profit']:
            return True, f"TAKE_PROFIT (+{pnl_percent*100:.1f}%)"
        
        # 2. Stop Loss: -1.5% desde entrada
        if pnl_percent <= -self.config['stop_loss']:
            return True, f"STOP_LOSS ({pnl_percent*100:.1f}%)"
        
        # 3. Tiempo: Máximo 24 horas en posición
        time_in_position = datetime.now() - entry_time
        if time_in_position > timedelta(hours=self.config['max_hold_hours']):
            hours = time_in_position.total_seconds() / 3600
            return True, f"TIME_STOP ({hours:.1f}h)"
        
        # 4. RSI > 75: Sobrecompra peligrosa
        try:
            df = self.binance.get_klines(symbol, self.config['timeframe'], 50)
            if not df.empty:
                analysis = self.analyzer.analyze_pair(df)
                if analysis.get('signal') == 'SELL':
                    rsi = analysis['data']['rsi']
                    return True, f"RSI_OVERBOUGHT ({rsi:.1f})"
        except:
            pass
        
        return False, ""
    
    def scan_for_opportunities(self):
        """Buscar oportunidades de trading según la estrategia"""
        # Verificar si podemos abrir más posiciones
        if len(self.positions) >= self.config['max_positions']:
            logging.info(f"📊 Máximo de posiciones alcanzado ({len(self.positions)}/{self.config['max_positions']})")
            return
        
        # Verificar balance disponible
        balance = self.binance.get_balance()
        available_usdt = balance.get('USDT', 0)
        
        if available_usdt < self.config['min_trade_amount']:
            logging.warning(f"💰 Balance insuficiente: ${available_usdt:.2f}")
            return
        
        logging.info(f"🔍 Analizando oportunidades en {len(self.trading_pairs)} pares...")
        
        # Analizar cada par
        opportunities = []
        
        for symbol in self.trading_pairs:
            if symbol in self.positions:
                continue  # Ya tenemos posición en este par
            
            # Verificar tiempo mínimo entre trades
            if self._is_too_soon_to_trade(symbol):
                continue
            
            try:
                # Obtener datos históricos
                df = self.binance.get_klines(symbol, self.config['timeframe'], 100)
                if df.empty:
                    continue
                
                # Analizar mercado
                analysis = self.analyzer.analyze_pair(df)
                
                # Verificar señal de compra con alta confianza
                if (analysis.get('signal') == 'BUY' and 
                    analysis.get('confidence', 0) >= 0.7):
                    
                    opportunities.append({
                        'symbol': symbol,
                        'analysis': analysis,
                        'confidence': analysis['confidence'],
                        'reason': analysis['reason']
                    })
                    
                    logging.info(f"📈 Oportunidad detectada: {symbol} - Confianza: {analysis['confidence']:.1%}")
                    logging.info(f"    Razón: {analysis['reason']}")
                    
            except Exception as e:
                logging.error(f"❌ Error analizando {symbol}: {e}")
        
        # Ordenar oportunidades por confianza
        opportunities.sort(key=lambda x: x['confidence'], reverse=True)
        
        # Ejecutar la mejor oportunidad
        if opportunities:
            best_opportunity = opportunities[0]
            logging.info(f"🚀 Ejecutando mejor oportunidad: {best_opportunity['symbol']} ({best_opportunity['confidence']:.1%})")
            self.execute_buy(best_opportunity)
    
    def _is_too_soon_to_trade(self, symbol: str) -> bool:
        """Verificar si es muy pronto para hacer otro trade en este símbolo"""
        if symbol not in self.last_trade_time:
            return False
            
        elapsed = time.time() - self.last_trade_time[symbol]
        return elapsed < self.config['min_time_between_trades']
    
    def execute_buy(self, opportunity: Dict):
        """Ejecutar compra según la estrategia"""
        symbol = opportunity['symbol']
        analysis = opportunity['analysis']
        
        try:
            # Obtener datos necesarios
            current_price = analysis['data']['price']
            confidence = analysis['confidence']
            
            # Calcular tamaño de posición (20% del balance)
            balance = self.binance.get_balance()
            available_usdt = balance.get('USDT', 0)
            position_size = available_usdt * self.config['position_size']
            
            # Verificar mínimo
            if position_size < self.config['min_trade_amount']:
                logging.warning(f"💰 Posición muy pequeña: ${position_size:.2f}")
                return
            
            logging.info(f"🔄 Ejecutando COMPRA: {symbol}")
            logging.info(f"    💰 Monto: ${position_size:.2f}")
            logging.info(f"    📊 Precio: ${current_price:.6f}")
            logging.info(f"    🎯 Confianza: {confidence:.1%}")
            
            # Ejecutar orden
            result = self.binance.place_market_buy(symbol, position_size)
            
            if result['success']:
                # Calcular stop loss y take profit
                entry_price = result['price']
                stop_loss = entry_price * (1 - self.config['stop_loss'])
                take_profit = entry_price * (1 + self.config['take_profit'])
                
                # Registrar posición
                self.positions[symbol] = {
                    'quantity': result['quantity'],
                    'entry_price': entry_price,
                    'entry_time': datetime.now(),
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'cost': result['cost'],
                    'fee': result['fee']
                }
                
                # Actualizar estadísticas
                self.total_fees += result['fee']
                self.daily_trades += 1
                self.last_trade_time[symbol] = time.time()
                
                # Log detallado
                logging.info(f"✅ COMPRA EXITOSA: {symbol}")
                logging.info(f"    📦 Cantidad: {result['quantity']:.8f}")
                logging.info(f"    💵 Precio entrada: ${entry_price:.6f}")
                logging.info(f"    💰 Costo total: ${result['cost']:.2f}")
                logging.info(f"    🚫 Stop Loss: ${stop_loss:.6f} (-{self.config['stop_loss']*100}%)")
                logging.info(f"    🎯 Take Profit: ${take_profit:.6f} (+{self.config['take_profit']*100}%)")
                logging.info(f"    💸 Comisión: ${result['fee']:.6f}")
                
                # Log para verificación
                self.log_trade('BUY', symbol, result)
                
            else:
                logging.error(f"❌ Error en compra {symbol}: {result['error']}")
                
        except Exception as e:
            logging.error(f"❌ Error ejecutando compra {symbol}: {e}")
    
    def execute_sell(self, symbol: str, quantity: float, current_price: float, reason: str):
        """Ejecutar venta y calcular resultados"""
        try:
            logging.info(f"🔄 Ejecutando VENTA: {symbol}")
            logging.info(f"    📦 Cantidad: {quantity:.8f}")
            logging.info(f"    💵 Precio actual: ${current_price:.6f}")
            logging.info(f"    📋 Razón: {reason}")
            
            # Ejecutar venta
            result = self.binance.place_market_sell(symbol, quantity)
            
            if result['success']:
                # Obtener datos de la posición
                position = self.positions[symbol]
                entry_price = position['entry_price']
                cost_basis = position['cost']
                entry_fee = position['fee']
                
                # Calcular resultados
                sale_proceeds = result['cost']
                sale_fee = result['fee']
                total_fees = entry_fee + sale_fee
                net_pnl = sale_proceeds - cost_basis - total_fees
                pnl_percent = (net_pnl / cost_basis) * 100
                
                # Actualizar estadísticas
                self.total_fees += sale_fee
                self.daily_trades += 1
                
                # Remover posición
                del self.positions[symbol]
                
                # Log detallado del resultado
                logging.info(f"✅ VENTA EXITOSA: {symbol}")
                logging.info(f"    📦 Cantidad vendida: {result['quantity']:.8f}")
                logging.info(f"    💵 Precio venta: ${result['price']:.6f}")
                logging.info(f"    💰 Ingresos: ${sale_proceeds:.2f}")
                logging.info(f"    💸 Comisión venta: ${sale_fee:.6f}")
                logging.info(f"    📊 RESULTADO:")
                logging.info(f"        💰 P&L Neto: ${net_pnl:.2f}")
                logging.info(f"        📈 P&L Porcentaje: {pnl_percent:+.2f}%")
                logging.info(f"        💸 Comisiones totales: ${total_fees:.6f}")
                logging.info(f"        ⏰ Tiempo en posición: {datetime.now() - position['entry_time']}")
                logging.info(f"        📋 Razón de salida: {reason}")
                
                # Log para verificación
                self.log_trade('SELL', symbol, result, net_pnl, pnl_percent)
                
                # Determinar si fue ganancia o pérdida
                if net_pnl > 0:
                    logging.info(f"🎉 GANANCIA REALIZADA: +${net_pnl:.2f} ({pnl_percent:+.2f}%)")
                else:
                    logging.info(f"📉 Pérdida realizada: ${net_pnl:.2f} ({pnl_percent:+.2f}%)")
                
            else:
                logging.error(f"❌ Error en venta {symbol}: {result['error']}")
                
        except Exception as e:
            logging.error(f"❌ Error ejecutando venta {symbol}: {e}")
    
    def log_trade(self, side: str, symbol: str, result: Dict, pnl: float = 0, pnl_percent: float = 0):
        """Registrar operación para verificación total"""
        trade_log = {
            'timestamp': datetime.now().isoformat(),
            'side': side,
            'symbol': symbol,
            'order_id': result.get('order_id'),
            'quantity': result['quantity'],
            'price': result['price'],
            'cost': result['cost'],
            'fee': result['fee'],
            'pnl': pnl,
            'pnl_percent': pnl_percent,
            'balance_after': self.binance.get_balance().get('USDT', 0)
        }
        
        # Guardar en archivo JSON para verificación
        filename = f'trades_{datetime.now().strftime("%Y%m%d")}.json'
        try:
            with open(filename, 'a', encoding='utf-8') as f:
                f.write(json.dumps(trade_log, ensure_ascii=False) + '\n')
        except Exception as e:
            logging.error(f"❌ Error guardando log de trade: {e}")
    
    def get_status_data(self) -> Dict:
            """Obtener datos de estado para la GUI"""
            try:
                balance = self.binance.get_balance()
                
                # Usar el balance total que incluye todas las criptomonedas
                usdt_free = balance.get('USDT', 0)
                total_account_value = balance.get('total_value_usdt', usdt_free)
                
                # Calcular valor de posiciones DEL BOT
                bot_positions_value = 0
                bot_positions_pnl = 0
                
                for symbol, position in self.positions.items():
                    try:
                        current_price = self.binance.get_price(symbol)
                        if current_price > 0:
                            position_value = position['quantity'] * current_price
                            bot_positions_value += position_value
                            
                            # P&L no realizado del bot
                            cost_basis = position['cost']
                            pnl = position_value - cost_basis
                            bot_positions_pnl += pnl
                    except:
                        pass
                
                # P&L total basado en balance inicial
                total_pnl = total_account_value - self.start_balance if self.start_balance > 0 else 0
                pnl_percent = (total_pnl / self.start_balance * 100) if self.start_balance > 0 else 0
                
                return {
                    'balance': usdt_free,                    # USDT libre
                    'total_account_value': total_account_value,  # Balance total real
                    'positions_value': bot_positions_value,      # Valor posiciones bot
                    'total_value': total_account_value,          # Para compatibilidad
                    'total_pnl': total_pnl,
                    'pnl_percent': pnl_percent,
                    'unrealized_pnl': bot_positions_pnl,
                    'active_positions': len(self.positions),
                    'daily_trades': self.daily_trades,
                    'total_fees': self.total_fees,
                    'positions': self.positions.copy(),
                    'is_running': self.is_running,
                    'cycles_completed': getattr(self, 'cycles_completed', 0)
                }
                
            except Exception as e:
                logging.error(f"❌ Error obteniendo datos de estado: {e}")
                return {}    
    
    def get_performance_summary(self) -> Dict:
        """Obtener resumen de rendimiento"""
        balance = self.binance.get_balance()
        current_balance = balance.get('USDT', 0)
        
        total_return = current_balance - self.start_balance if self.start_balance > 0 else 0
        return_percent = (total_return / self.start_balance * 100) if self.start_balance > 0 else 0
        
        return {
            'start_balance': self.start_balance,
            'current_balance': current_balance,
            'total_return': total_return,
            'return_percent': return_percent,
            'total_trades': self.daily_trades,
            'total_fees': self.total_fees,
            'positions_count': len(self.positions)
        }