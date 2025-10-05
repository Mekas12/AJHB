from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import json
from datetime import datetime
import os
import logging
from functools import wraps
import time
from threading import Lock

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ajhb_ventas.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Lock para operaciones de base de datos
db_lock = Lock()

# Configuración de la base de datos
DB_NAME = 'ajhb_ventas.db'

def get_db():
    """Obtener conexión a la base de datos con reintentos"""
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=20.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA cache_size=10000')
            conn.execute('PRAGMA temp_store=MEMORY')
            return conn
        except sqlite3.Error as e:
            logger.error(f"Error conectando a la base de datos (intento {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                raise

def init_db():
    """Inicializar la base de datos con todas las tablas"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Tabla de Propiedades
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            operation TEXT,
            address TEXT,
            provincia TEXT,
            canton TEXT,
            latitud REAL,
            longitud REAL,
            price REAL,
            bedrooms INTEGER,
            bathrooms INTEGER,
            area REAL,
            status TEXT DEFAULT 'disponible',
            estado TEXT DEFAULT 'disponible',
            description TEXT,
            dateAdded TEXT,
            createdAt TEXT,
            soldAt TEXT
        )
    ''')
    
    # Migración: Agregar columnas si no existen
    try:
        cursor.execute("SELECT provincia FROM properties LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("🔧 Agregando columnas de ubicación a properties...")
        cursor.execute("ALTER TABLE properties ADD COLUMN provincia TEXT")
        cursor.execute("ALTER TABLE properties ADD COLUMN canton TEXT")
        cursor.execute("ALTER TABLE properties ADD COLUMN latitud REAL")
        cursor.execute("ALTER TABLE properties ADD COLUMN longitud REAL")
        cursor.execute("ALTER TABLE properties ADD COLUMN estado TEXT DEFAULT 'disponible'")
        conn.commit()
        logger.info("✅ Columnas de ubicación agregadas")
    
    # Tabla de Clientes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            interest TEXT,
            budget REAL,
            notes TEXT,
            dateAdded TEXT,
            createdAt TEXT
        )
    ''')
    
    # Tabla de Contratos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            propertyId INTEGER,
            propertyInfo TEXT,
            clientId INTEGER,
            clientName TEXT,
            type TEXT,
            value REAL,
            date TEXT,
            terms TEXT,
            status TEXT DEFAULT 'Activo',
            dateAdded TEXT,
            createdAt TEXT,
            FOREIGN KEY (propertyId) REFERENCES properties(id),
            FOREIGN KEY (clientId) REFERENCES clients(id)
        )
    ''')
    
    # Tabla de Prospectos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prospects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            source TEXT,
            interest TEXT,
            budget REAL,
            notes TEXT,
            status TEXT DEFAULT 'Nuevo',
            dateAdded TEXT,
            createdAt TEXT
        )
    ''')
    
    # Tabla de Citas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            clientId INTEGER,
            clientName TEXT,
            propertyId INTEGER,
            propertyInfo TEXT,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            type TEXT,
            notes TEXT,
            reminder INTEGER DEFAULT 30,
            status TEXT DEFAULT 'Programada',
            dateAdded TEXT,
            createdAt TEXT,
            FOREIGN KEY (clientId) REFERENCES clients(id),
            FOREIGN KEY (propertyId) REFERENCES properties(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Base de datos inicializada correctamente")

# Inicializar la base de datos al arrancar
init_db()

# ==================== RUTAS API ====================

@app.route('/')
def index():
    """Servir la página principal"""
    return send_from_directory('.', 'DepVentas.html')

@app.route('/api/health', methods=['GET'])
def health_check():
    """Verificar estado del servidor"""
    return jsonify({'status': 'ok', 'message': 'Backend de ventas funcionando correctamente'})

# ==================== PROPIEDADES ====================

@app.route('/api/properties', methods=['GET'])
def get_properties():
    """Obtener todas las propiedades"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM properties ORDER BY id DESC')
        rows = cursor.fetchall()
        conn.close()
        
        properties = [dict(row) for row in rows]
        return jsonify({'data': properties, '_0x4a5b': properties})
    except Exception as e:
        logger.error(f"Error obteniendo propiedades: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/properties/<int:id>', methods=['GET'])
def get_property(id):
    """Obtener una propiedad por ID"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM properties WHERE id = ?', (id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return jsonify(dict(row))
        return jsonify({'error': 'Propiedad no encontrada'}), 404
    except Exception as e:
        logger.error(f"Error obteniendo propiedad {id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/properties', methods=['POST'])
def create_property():
    """Crear una nueva propiedad"""
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO properties (type, operation, address, provincia, canton, latitud, longitud, 
                                  price, bedrooms, bathrooms, area, status, estado, description, dateAdded, createdAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('type'),
            data.get('operation'),
            data.get('address'),
            data.get('provincia'),
            data.get('canton'),
            data.get('latitud'),
            data.get('longitud'),
            data.get('price'),
            data.get('bedrooms'),
            data.get('bathrooms'),
            data.get('area'),
            data.get('status', 'disponible'),
            data.get('estado', 'disponible'),
            data.get('description'),
            data.get('dateAdded'),
            data.get('createdAt')
        ))
        
        property_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Propiedad creada con ID: {property_id} en {data.get('provincia')}, {data.get('canton')}")
        return jsonify({'id': property_id, '_0x9e7f': property_id, 'success': True})
    except Exception as e:
        logger.error(f"Error creando propiedad: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/propiedades', methods=['GET'])
def get_propiedades():
    """Obtener todas las propiedades (alias en español)"""
    return get_properties()

@app.route('/api/properties/<int:id>', methods=['PUT'])
def update_property(id):
    """Actualizar una propiedad"""
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        # Construir query dinámicamente basado en los campos proporcionados
        fields = []
        values = []
        
        for field in ['type', 'operation', 'address', 'price', 'bedrooms', 'bathrooms', 'area', 'status', 'description', 'soldAt']:
            if field in data:
                fields.append(f"{field} = ?")
                values.append(data[field])
        
        if not fields:
            return jsonify({'error': 'No hay campos para actualizar'}), 400
        
        values.append(id)
        query = f"UPDATE properties SET {', '.join(fields)} WHERE id = ?"
        
        cursor.execute(query, values)
        conn.commit()
        conn.close()
        
        logger.info(f"Propiedad {id} actualizada")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error actualizando propiedad {id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/properties/<int:id>', methods=['DELETE'])
def delete_property(id):
    """Eliminar una propiedad"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM properties WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        
        logger.info(f"Propiedad {id} eliminada")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error eliminando propiedad {id}: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== CLIENTES ====================

@app.route('/api/clients', methods=['GET'])
def get_clients():
    """Obtener todos los clientes"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM clients ORDER BY id DESC')
        rows = cursor.fetchall()
        conn.close()
        
        clients = [dict(row) for row in rows]
        return jsonify({'data': clients, '_0x4a5b': clients})
    except Exception as e:
        logger.error(f"Error obteniendo clientes: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/clients/<int:id>', methods=['GET'])
def get_client(id):
    """Obtener un cliente por ID"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM clients WHERE id = ?', (id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return jsonify(dict(row))
        return jsonify({'error': 'Cliente no encontrado'}), 404
    except Exception as e:
        logger.error(f"Error obteniendo cliente {id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/clients', methods=['POST'])
def create_client():
    """Crear un nuevo cliente"""
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO clients (name, email, phone, interest, budget, notes, dateAdded, createdAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('name'),
            data.get('email'),
            data.get('phone'),
            data.get('interest'),
            data.get('budget'),
            data.get('notes'),
            data.get('dateAdded'),
            data.get('createdAt')
        ))
        
        client_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Cliente creado con ID: {client_id}")
        return jsonify({'id': client_id, '_0x9e7f': client_id, 'success': True})
    except sqlite3.IntegrityError as e:
        logger.error(f"Error de integridad creando cliente: {e}")
        return jsonify({'error': 'El email ya está registrado'}), 400
    except Exception as e:
        logger.error(f"Error creando cliente: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/clients/<int:id>', methods=['PUT'])
def update_client(id):
    """Actualizar un cliente"""
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        fields = []
        values = []
        
        for field in ['name', 'email', 'phone', 'interest', 'budget', 'notes']:
            if field in data:
                fields.append(f"{field} = ?")
                values.append(data[field])
        
        if not fields:
            return jsonify({'error': 'No hay campos para actualizar'}), 400
        
        values.append(id)
        query = f"UPDATE clients SET {', '.join(fields)} WHERE id = ?"
        
        cursor.execute(query, values)
        conn.commit()
        conn.close()
        
        logger.info(f"Cliente {id} actualizado")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error actualizando cliente {id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/clients/<int:id>', methods=['DELETE'])
def delete_client(id):
    """Eliminar un cliente"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM clients WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        
        logger.info(f"Cliente {id} eliminado")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error eliminando cliente {id}: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== CONTRATOS ====================

@app.route('/api/contracts', methods=['GET'])
def get_contracts():
    """Obtener todos los contratos"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM contracts ORDER BY id DESC')
        rows = cursor.fetchall()
        conn.close()
        
        contracts = [dict(row) for row in rows]
        return jsonify({'data': contracts, '_0x4a5b': contracts})
    except Exception as e:
        logger.error(f"Error obteniendo contratos: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/contracts/<int:id>', methods=['GET'])
def get_contract(id):
    """Obtener un contrato por ID"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM contracts WHERE id = ?', (id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return jsonify(dict(row))
        return jsonify({'error': 'Contrato no encontrado'}), 404
    except Exception as e:
        logger.error(f"Error obteniendo contrato {id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/contracts', methods=['POST'])
def create_contract():
    """Crear un nuevo contrato"""
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO contracts (propertyId, propertyInfo, clientId, clientName, type, value, date, terms, status, dateAdded, createdAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('propertyId'),
            data.get('propertyInfo'),
            data.get('clientId'),
            data.get('clientName'),
            data.get('type'),
            data.get('value'),
            data.get('date'),
            data.get('terms'),
            data.get('status', 'Activo'),
            data.get('dateAdded'),
            data.get('createdAt')
        ))
        
        contract_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Contrato creado con ID: {contract_id}")
        return jsonify({'id': contract_id, '_0x9e7f': contract_id, 'success': True})
    except Exception as e:
        logger.error(f"Error creando contrato: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/contracts/<int:id>', methods=['PUT'])
def update_contract(id):
    """Actualizar un contrato"""
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        fields = []
        values = []
        
        for field in ['propertyId', 'propertyInfo', 'clientId', 'clientName', 'type', 'value', 'date', 'terms', 'status']:
            if field in data:
                fields.append(f"{field} = ?")
                values.append(data[field])
        
        if not fields:
            return jsonify({'error': 'No hay campos para actualizar'}), 400
        
        values.append(id)
        query = f"UPDATE contracts SET {', '.join(fields)} WHERE id = ?"
        
        cursor.execute(query, values)
        conn.commit()
        conn.close()
        
        logger.info(f"Contrato {id} actualizado")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error actualizando contrato {id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/contracts/<int:id>', methods=['DELETE'])
def delete_contract(id):
    """Eliminar un contrato"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM contracts WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        
        logger.info(f"Contrato {id} eliminado")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error eliminando contrato {id}: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== PROSPECTOS ====================

@app.route('/api/prospects', methods=['GET'])
def get_prospects():
    """Obtener todos los prospectos"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM prospects ORDER BY id DESC')
        rows = cursor.fetchall()
        conn.close()
        
        prospects = [dict(row) for row in rows]
        return jsonify({'data': prospects, '_0x4a5b': prospects})
    except Exception as e:
        logger.error(f"Error obteniendo prospectos: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/prospects', methods=['POST'])
def create_prospect():
    """Crear un nuevo prospecto"""
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO prospects (name, email, phone, source, interest, budget, notes, status, dateAdded, createdAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('name'),
            data.get('email'),
            data.get('phone'),
            data.get('source'),
            data.get('interest'),
            data.get('budget'),
            data.get('notes'),
            data.get('status', 'Nuevo'),
            data.get('dateAdded'),
            data.get('createdAt')
        ))
        
        prospect_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Prospecto creado con ID: {prospect_id}")
        return jsonify({'id': prospect_id, '_0x9e7f': prospect_id, 'success': True})
    except Exception as e:
        logger.error(f"Error creando prospecto: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/prospects/<int:id>', methods=['PUT'])
def update_prospect(id):
    """Actualizar un prospecto"""
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        fields = []
        values = []
        
        for field in ['name', 'email', 'phone', 'source', 'interest', 'budget', 'notes', 'status']:
            if field in data:
                fields.append(f"{field} = ?")
                values.append(data[field])
        
        if not fields:
            return jsonify({'error': 'No hay campos para actualizar'}), 400
        
        values.append(id)
        query = f"UPDATE prospects SET {', '.join(fields)} WHERE id = ?"
        
        cursor.execute(query, values)
        conn.commit()
        conn.close()
        
        logger.info(f"Prospecto {id} actualizado")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error actualizando prospecto {id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/prospects/<int:id>', methods=['DELETE'])
def delete_prospect(id):
    """Eliminar un prospecto"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM prospects WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        
        logger.info(f"Prospecto {id} eliminado")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error eliminando prospecto {id}: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== CITAS ====================

@app.route('/api/appointments', methods=['GET'])
def get_appointments():
    """Obtener todas las citas"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM appointments ORDER BY date DESC, time DESC')
        rows = cursor.fetchall()
        conn.close()
        
        appointments = [dict(row) for row in rows]
        return jsonify({'data': appointments, '_0x4a5b': appointments})
    except Exception as e:
        logger.error(f"Error obteniendo citas: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/appointments', methods=['POST'])
def create_appointment():
    """Crear una nueva cita"""
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO appointments (title, clientId, clientName, propertyId, propertyInfo, date, time, type, notes, reminder, status, dateAdded, createdAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('title'),
            data.get('clientId'),
            data.get('clientName'),
            data.get('propertyId'),
            data.get('propertyInfo'),
            data.get('date'),
            data.get('time'),
            data.get('type'),
            data.get('notes'),
            data.get('reminder', 30),
            data.get('status', 'Programada'),
            data.get('dateAdded'),
            data.get('createdAt')
        ))
        
        appointment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Cita creada con ID: {appointment_id}")
        return jsonify({'id': appointment_id, '_0x9e7f': appointment_id, 'success': True})
    except Exception as e:
        logger.error(f"Error creando cita: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/appointments/<int:id>', methods=['PUT'])
def update_appointment(id):
    """Actualizar una cita"""
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        fields = []
        values = []
        
        for field in ['title', 'clientId', 'clientName', 'propertyId', 'propertyInfo', 'date', 'time', 'type', 'notes', 'reminder', 'status']:
            if field in data:
                fields.append(f"{field} = ?")
                values.append(data[field])
        
        if not fields:
            return jsonify({'error': 'No hay campos para actualizar'}), 400
        
        values.append(id)
        query = f"UPDATE appointments SET {', '.join(fields)} WHERE id = ?"
        
        cursor.execute(query, values)
        conn.commit()
        conn.close()
        
        logger.info(f"Cita {id} actualizada")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error actualizando cita {id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/appointments/<int:id>', methods=['DELETE'])
def delete_appointment(id):
    """Eliminar una cita"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM appointments WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        
        logger.info(f"Cita {id} eliminada")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error eliminando cita {id}: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== SERVIDOR ====================

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 AJHB Backend de Ventas - Sistema Inmobiliario")
    print("=" * 60)
    print(f"📁 Base de datos: {DB_NAME}")
    print("🌐 Servidor corriendo en: http://localhost:5001")
    print("📡 API disponible en: http://localhost:5001/api/")
    print("=" * 60)
    print("\n✅ Servidor iniciado correctamente\n")
    
    app.run(host='0.0.0.0', port=5001, debug=True, threaded=True)
