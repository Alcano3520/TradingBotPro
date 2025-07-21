#!/usr/bin/env python3
"""
SCRIPT DE LIMPIEZA PARA TRADING BOT
Ejecutar ANTES de iniciar el bot para limpiar datos corruptos
"""

import os
import json
import shutil
from datetime import datetime
from pathlib import Path

def cleanup_bot_data():
    """Limpiar todos los datos que pueden causar problemas"""
    
    print("🧹 INICIANDO LIMPIEZA DE DATOS DEL BOT...")
    
    # 1. Limpiar archivos de configuración corruptos
    files_to_check = [
        'trading_config.json',
        'trading_bot.lock',
        'bot_state.json',
        'positions.json'
    ]
    
    for file in files_to_check:
        if os.path.exists(file):
            try:
                # Hacer backup antes de eliminar
                backup_name = f"{file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(file, backup_name)
                os.remove(file)
                print(f"✅ {file} eliminado (backup: {backup_name})")
            except Exception as e:
                print(f"⚠️ Error con {file}: {e}")
    
    # 2. Limpiar logs antiguos que pueden causar problemas
    log_dir = Path("logs")
    if log_dir.exists():
        for log_file in log_dir.glob("*.log"):
            if log_file.stat().st_size > 50 * 1024 * 1024:  # > 50MB
                try:
                    log_file.unlink()
                    print(f"✅ Log grande eliminado: {log_file}")
                except Exception as e:
                    print(f"⚠️ Error eliminando {log_file}: {e}")
    
    # 3. Limpiar archivos de trades que pueden estar corruptos
    trade_files = list(Path(".").glob("trades_*.json"))
    for trade_file in trade_files:
        try:
            # Verificar si el archivo está corrupto
            with open(trade_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    if line.strip():  # Skip empty lines
                        json.loads(line)  # Verificar JSON válido
            print(f"✅ {trade_file} - JSON válido")
        except (json.JSONDecodeError, Exception) as e:
            try:
                backup_name = f"{trade_file}.corrupted_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.move(str(trade_file), backup_name)
                print(f"🚨 {trade_file} corrupto - movido a {backup_name}")
            except Exception as e2:
                print(f"❌ Error moviendo archivo corrupto: {e2}")
    
    # 4. Crear configuración limpia
    clean_config = {
        "api_key": "",
        "api_secret": "",
        "testnet": True,
        "saved_at": datetime.now().isoformat(),
        "cleaned": True
    }
    
    try:
        with open('trading_config.json', 'w') as f:
            json.dump(clean_config, f, indent=4)
        print("✅ Configuración limpia creada")
    except Exception as e:
        print(f"⚠️ Error creando configuración: {e}")
    
    print("🎉 LIMPIEZA COMPLETADA")
    print("💡 Ahora puedes iniciar el bot sin problemas")
    print("⚠️ Recuerda reconfigurar tus API keys")

if __name__ == "__main__":
    cleanup_bot_data()


# ADEMÁS - Función para añadir al inicio de main.py

def emergency_cleanup():
    """Limpieza de emergencia al iniciar el bot"""
    try:
        # Verificar si hay archivo de bloqueo antiguo
        lock_file = Path("trading_bot.lock")
        if lock_file.exists():
            # Verificar si es muy antiguo (más de 1 hora)
            lock_age = time.time() - lock_file.stat().st_mtime
            if lock_age > 3600:  # 1 hora
                lock_file.unlink()
                logging.info("🧹 Archivo de bloqueo antiguo eliminado")
        
        # Verificar archivos de configuración corruptos
        config_file = Path("trading_config.json")
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    json.load(f)  # Verificar JSON válido
            except json.JSONDecodeError:
                backup = f"trading_config.corrupted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                shutil.move(str(config_file), backup)
                logging.warning(f"⚠️ Configuración corrupta movida a {backup}")
        
        # Limpiar memoria de procesos zombies
        import gc
        gc.collect()
        
        logging.info("✅ Limpieza de emergencia completada")
        
    except Exception as e:
        logging.error(f"❌ Error en limpieza de emergencia: {e}")


# Llamar al inicio de main() en main.py:
def main():
    try:
        # AÑADIR ESTA LÍNEA AL INICIO
        emergency_cleanup()
        
        # Resto del código de main()...