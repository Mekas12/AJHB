from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import json
from datetime import datetime
import os
import sys
import logging
from functools import wraps
import time
from threading import Lock

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ajhb_backend.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Lock para operaciones de base de datos
db_lock = Lock()

# Configuración de la base de datos
DB_NAME = 'ajhb_crm.db'

def get_db():
    """Obtener conexión a la base de datos con reintentos"""
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(DB_NAME, timeout=20.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA journal_mode=WAL')  # Write-Ahead Logging para mejor concurrencia
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

def retry_on_db_error(max_retries=3):
    """Decorador para reintentar operaciones de base de datos"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    logger.warning(f"Error de BD en {func.__name__} (intento {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        time.sleep(0.5 * (attempt + 1))
                    else:
                        raise
                except Exception as e:
                    logger.error(f"Error en {func.__name__}: {e}")
                    raise
            return None
        return wrapper
    return decorator

def init_db():
    """Inicializar la base de datos con todas las tablas"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Tabla de Clientes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            cedula TEXT,
            email TEXT,
            telefono TEXT,
            telefonoAlt TEXT,
            direccion TEXT,
            empresa TEXT,
            tipoCliente TEXT DEFAULT 'regular',
            descuento REAL DEFAULT 0,
            notas TEXT,
            fechaRegistro TEXT
        )
    ''')
    
    # Tabla de Vouchers
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vouchers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clienteId INTEGER,
            tipoComprobante TEXT,
            numeroComprobante TEXT,
            fecha TEXT,
            total REAL,
            fechaCreacion TEXT,
            FOREIGN KEY (clienteId) REFERENCES clientes(id)
        )
    ''')
    
    # Tabla de Notas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            contenido TEXT NOT NULL,
            categoria TEXT DEFAULT 'general',
            prioridad TEXT DEFAULT 'media',
            etiquetas TEXT,
            archivada INTEGER DEFAULT 0,
            fecha TEXT,
            fechaModificacion TEXT,
            caracteres INTEGER DEFAULT 0,
            palabras INTEGER DEFAULT 0
        )
    ''')
    
    # Tabla de Eventos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            fecha TEXT NOT NULL,
            tipo TEXT,
            descripcion TEXT,
            fechaCreacion TEXT
        )
    ''')
    
    # Tabla de Cuentas Contables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cuentas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            tipo TEXT NOT NULL,
            categoria TEXT,
            nivel INTEGER,
            padre TEXT,
            saldo REAL DEFAULT 0
        )
    ''')
    
    # Tabla de Asientos Contables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS asientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT UNIQUE NOT NULL,
            fecha TEXT NOT NULL,
            tipo TEXT,
            descripcion TEXT,
            totalDebe REAL,
            totalHaber REAL,
            estado TEXT DEFAULT 'activo',
            fechaCreacion TEXT
        )
    ''')
    
    # Tabla de Detalles de Asientos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS detallesAsiento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asientoId INTEGER,
            cuentaId INTEGER,
            debe REAL DEFAULT 0,
            haber REAL DEFAULT 0,
            FOREIGN KEY (asientoId) REFERENCES asientos(id),
            FOREIGN KEY (cuentaId) REFERENCES cuentas(id)
        )
    ''')
    
    # Tabla de Proveedores
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            cedula TEXT,
            email TEXT,
            telefono TEXT,
            direccion TEXT,
            saldo REAL DEFAULT 0,
            fechaRegistro TEXT
        )
    ''')
    
    # Tabla de Cuentas por Cobrar
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cuentasPorCobrar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clienteId INTEGER,
            numeroFactura TEXT,
            monto REAL,
            saldo REAL,
            fechaEmision TEXT,
            fechaVencimiento TEXT,
            descripcion TEXT,
            estado TEXT DEFAULT 'pendiente',
            fechaCreacion TEXT,
            FOREIGN KEY (clienteId) REFERENCES clientes(id)
        )
    ''')
    
    # Tabla de Cuentas por Pagar
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cuentasPorPagar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proveedorId INTEGER,
            numeroFactura TEXT,
            monto REAL,
            saldo REAL,
            fechaEmision TEXT,
            fechaVencimiento TEXT,
            descripcion TEXT,
            estado TEXT DEFAULT 'pendiente',
            fechaCreacion TEXT,
            FOREIGN KEY (proveedorId) REFERENCES proveedores(id)
        )
    ''')
    
    # Tabla de Activos Fijos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descripcion TEXT NOT NULL,
            categoria TEXT,
            valorCompra REAL,
            valorResidual REAL DEFAULT 0,
            vidaUtil INTEGER,
            depreciacionAnual REAL,
            depreciacionAcumulada REAL DEFAULT 0,
            valorEnLibros REAL,
            fechaCompra TEXT,
            proveedor TEXT,
            estado TEXT DEFAULT 'activo',
            fechaRegistro TEXT
        )
    ''')
    
    # Tabla de Bancos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bancos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            numeroCuenta TEXT,
            tipo TEXT,
            saldo REAL DEFAULT 0,
            fechaApertura TEXT
        )
    ''')
    
    # Tabla de Movimientos Bancarios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movimientosBancarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bancoId INTEGER,
            tipo TEXT,
            monto REAL,
            fecha TEXT,
            descripcion TEXT,
            saldoResultante REAL,
            fechaRegistro TEXT,
            FOREIGN KEY (bancoId) REFERENCES bancos(id)
        )
    ''')
    
    # Tabla de Presupuestos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS presupuestos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            periodo TEXT,
            monto REAL,
            gastado REAL DEFAULT 0,
            categoria TEXT,
            fechaCreacion TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Base de datos inicializada correctamente")

# ==================== RUTAS GENÉRICAS ====================

@app.route('/api/<tabla>', methods=['GET'])
@retry_on_db_error(max_retries=3)
def get_all(tabla):
    """Obtener todos los registros de una tabla"""
    try:
        with db_lock:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(f'SELECT * FROM {tabla}')
            rows = cursor.fetchall()
            conn.close()
        
        items = [dict(row) for row in rows]
        logger.info(f"GET /api/{tabla} - {len(items)} registros")
        return jsonify(items), 200
    except sqlite3.OperationalError as e:
        logger.error(f"Error de BD en GET /api/{tabla}: {e}")
        return jsonify({'error': 'Error de base de datos', 'details': str(e)}), 503
    except Exception as e:
        logger.error(f"Error en GET /api/{tabla}: {e}")
        return jsonify({'error': 'Error interno del servidor', 'details': str(e)}), 500

@app.route('/api/<tabla>/<int:id>', methods=['GET'])
@retry_on_db_error(max_retries=3)
def get_one(tabla, id):
    """Obtener un registro específico"""
    try:
        with db_lock:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(f'SELECT * FROM {tabla} WHERE id = ?', (id,))
            row = cursor.fetchone()
            conn.close()
        
        if row:
            logger.info(f"GET /api/{tabla}/{id} - Encontrado")
            return jsonify(dict(row)), 200
        logger.warning(f"GET /api/{tabla}/{id} - No encontrado")
        return jsonify({'error': 'No encontrado'}), 404
    except Exception as e:
        logger.error(f"Error en GET /api/{tabla}/{id}: {e}")
        return jsonify({'error': 'Error interno del servidor', 'details': str(e)}), 500

@app.route('/api/<tabla>', methods=['POST'])
@retry_on_db_error(max_retries=3)
def create(tabla):
    """Crear un nuevo registro"""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No se enviaron datos'}), 400
        
        with db_lock:
            conn = get_db()
            cursor = conn.cursor()
            
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data])
            query = f'INSERT INTO {tabla} ({columns}) VALUES ({placeholders})'
            
            cursor.execute(query, list(data.values()))
            conn.commit()
            new_id = cursor.lastrowid
            conn.close()
        
        logger.info(f"POST /api/{tabla} - Creado ID: {new_id}")
        return jsonify({'id': new_id, 'message': 'Creado exitosamente'}), 201
    except sqlite3.IntegrityError as e:
        logger.warning(f"Error de integridad en POST /api/{tabla}: {e}")
        return jsonify({'error': 'Error de integridad de datos', 'details': str(e)}), 409
    except Exception as e:
        logger.error(f"Error en POST /api/{tabla}: {e}")
        return jsonify({'error': 'Error interno del servidor', 'details': str(e)}), 500

@app.route('/api/<tabla>/<int:id>', methods=['PUT'])
@retry_on_db_error(max_retries=3)
def update(tabla, id):
    """Actualizar un registro"""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No se enviaron datos'}), 400
        
        with db_lock:
            conn = get_db()
            cursor = conn.cursor()
            
            set_clause = ', '.join([f'{key} = ?' for key in data.keys()])
            query = f'UPDATE {tabla} SET {set_clause} WHERE id = ?'
            
            values = list(data.values()) + [id]
            cursor.execute(query, values)
            affected = cursor.rowcount
            conn.commit()
            conn.close()
        
        if affected > 0:
            logger.info(f"PUT /api/{tabla}/{id} - Actualizado")
            return jsonify({'message': 'Actualizado exitosamente'}), 200
        else:
            logger.warning(f"PUT /api/{tabla}/{id} - No encontrado")
            return jsonify({'error': 'Registro no encontrado'}), 404
    except Exception as e:
        logger.error(f"Error en PUT /api/{tabla}/{id}: {e}")
        return jsonify({'error': 'Error interno del servidor', 'details': str(e)}), 500

@app.route('/api/<tabla>/<int:id>', methods=['DELETE'])
@retry_on_db_error(max_retries=3)
def delete(tabla, id):
    """Eliminar un registro"""
    try:
        with db_lock:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(f'DELETE FROM {tabla} WHERE id = ?', (id,))
            affected = cursor.rowcount
            conn.commit()
            conn.close()
        
        if affected > 0:
            logger.info(f"DELETE /api/{tabla}/{id} - Eliminado")
            return jsonify({'message': 'Eliminado exitosamente'}), 200
        else:
            logger.warning(f"DELETE /api/{tabla}/{id} - No encontrado")
            return jsonify({'error': 'Registro no encontrado'}), 404
    except Exception as e:
        logger.error(f"Error en DELETE /api/{tabla}/{id}: {e}")
        return jsonify({'error': 'Error interno del servidor', 'details': str(e)}), 500

# ==================== RUTAS ESPECIALES ====================

@app.route('/api/cuentas/inicializar', methods=['POST'])
def inicializar_cuentas():
    """Inicializar catálogo de cuentas contables"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Verificar si ya existen cuentas
        cursor.execute('SELECT COUNT(*) as count FROM cuentas')
        count = cursor.fetchone()['count']
        
        if count > 0:
            conn.close()
            return jsonify({'message': 'Catálogo ya inicializado'}), 200
        
        cuentas_base = [
            ('1', 'ACTIVO', 'activo', 'grupo', 1, None),
            ('1.1', 'ACTIVO CORRIENTE', 'activo', 'subgrupo', 2, '1'),
            ('1.1.1', 'Efectivo y Equivalentes', 'activo', 'cuenta', 3, '1.1'),
            ('1.1.1.01', 'Caja General', 'activo', 'subcuenta', 4, '1.1.1'),
            ('1.1.1.02', 'Bancos', 'activo', 'subcuenta', 4, '1.1.1'),
            ('1.1.2', 'Cuentas por Cobrar', 'activo', 'cuenta', 3, '1.1'),
            ('1.1.2.01', 'Clientes', 'activo', 'subcuenta', 4, '1.1.2'),
            ('1.2', 'ACTIVO NO CORRIENTE', 'activo', 'subgrupo', 2, '1'),
            ('1.2.1', 'Propiedad, Planta y Equipo', 'activo', 'cuenta', 3, '1.2'),
            ('1.2.1.01', 'Terrenos', 'activo', 'subcuenta', 4, '1.2.1'),
            ('1.2.1.02', 'Edificios', 'activo', 'subcuenta', 4, '1.2.1'),
            ('1.2.1.03', 'Mobiliario y Equipo', 'activo', 'subcuenta', 4, '1.2.1'),
            ('1.2.2', 'Depreciación Acumulada', 'activo', 'cuenta', 3, '1.2'),
            ('2', 'PASIVO', 'pasivo', 'grupo', 1, None),
            ('2.1', 'PASIVO CORRIENTE', 'pasivo', 'subgrupo', 2, '2'),
            ('2.1.1', 'Cuentas por Pagar', 'pasivo', 'cuenta', 3, '2.1'),
            ('2.1.1.01', 'Proveedores', 'pasivo', 'subcuenta', 4, '2.1.1'),
            ('2.1.2', 'Impuestos por Pagar', 'pasivo', 'cuenta', 3, '2.1'),
            ('2.1.2.01', 'IVA por Pagar', 'pasivo', 'subcuenta', 4, '2.1.2'),
            ('3', 'PATRIMONIO', 'patrimonio', 'grupo', 1, None),
            ('3.1', 'Capital Social', 'patrimonio', 'cuenta', 2, '3'),
            ('3.2', 'Utilidades Retenidas', 'patrimonio', 'cuenta', 2, '3'),
            ('3.3', 'Utilidad del Ejercicio', 'patrimonio', 'cuenta', 2, '3'),
            ('4', 'INGRESOS', 'ingreso', 'grupo', 1, None),
            ('4.1', 'Ingresos Operacionales', 'ingreso', 'subgrupo', 2, '4'),
            ('4.1.1', 'Ventas', 'ingreso', 'cuenta', 3, '4.1'),
            ('4.1.1.01', 'Ventas de Bienes Raíces', 'ingreso', 'subcuenta', 4, '4.1.1'),
            ('4.1.2', 'Servicios', 'ingreso', 'cuenta', 3, '4.1'),
            ('5', 'GASTOS', 'gasto', 'grupo', 1, None),
            ('5.1', 'Gastos Operacionales', 'gasto', 'subgrupo', 2, '5'),
            ('5.1.1', 'Gastos de Administración', 'gasto', 'cuenta', 3, '5.1'),
            ('5.1.1.01', 'Sueldos y Salarios', 'gasto', 'subcuenta', 4, '5.1.1'),
            ('5.1.1.02', 'Servicios Públicos', 'gasto', 'subcuenta', 4, '5.1.1'),
            ('5.1.2', 'Gastos de Ventas', 'gasto', 'cuenta', 3, '5.1'),
            ('5.1.2.01', 'Publicidad', 'gasto', 'subcuenta', 4, '5.1.2'),
            ('5.1.2.02', 'Comisiones', 'gasto', 'subcuenta', 4, '5.1.2'),
        ]
        
        for cuenta in cuentas_base:
            cursor.execute('''
                INSERT INTO cuentas (codigo, nombre, tipo, categoria, nivel, padre, saldo)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            ''', cuenta)
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Catálogo inicializado exitosamente'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats/dashboard', methods=['GET'])
def dashboard_stats():
    """Obtener estadísticas para el dashboard"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) as count FROM clientes')
        total_clientes = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as count FROM asientos')
        total_asientos = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as count FROM activos')
        total_activos = cursor.fetchone()['count']
        
        cursor.execute('SELECT SUM(saldo) as total FROM cuentasPorCobrar WHERE estado = "pendiente"')
        cuentas_cobrar = cursor.fetchone()['total'] or 0
        
        cursor.execute('SELECT SUM(saldo) as total FROM cuentasPorPagar WHERE estado = "pendiente"')
        cuentas_pagar = cursor.fetchone()['total'] or 0
        
        cursor.execute('SELECT SUM(saldo) as total FROM bancos')
        saldo_bancos = cursor.fetchone()['total'] or 0
        
        conn.close()
        
        return jsonify({
            'totalClientes': total_clientes,
            'totalAsientos': total_asientos,
            'totalActivos': total_activos,
            'cuentasCobrar': cuentas_cobrar,
            'cuentasPagar': cuentas_pagar,
            'saldoBancos': saldo_bancos
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Verificar estado del servidor"""
    return jsonify({
        'status': 'ok',
        'message': 'AJHB Backend funcionando correctamente',
        'timestamp': datetime.now().isoformat()
    }), 200

# ==================== MANEJO DE ERRORES GLOBAL ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Recurso no encontrado'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Error 500: {error}")
    return jsonify({'error': 'Error interno del servidor'}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Excepción no manejada: {e}", exc_info=True)
    return jsonify({'error': 'Error inesperado', 'details': str(e)}), 500

# ==================== MIDDLEWARE ====================

@app.before_request
def log_request():
    logger.info(f"{request.method} {request.path} - IP: {request.remote_addr}")

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# ==================== RUTAS ESTÁTICAS ====================

@app.route('/')
def index():
    """Servir página principal de Contaduría"""
    return send_from_directory('.', 'Depconta.html')

@app.route('/<path:path>')
def serve_static(path):
    """Servir archivos estáticos (HTML, CSS, JS)"""
    # No servir rutas de API como archivos estáticos
    if path.startswith('api/'):
        return jsonify({'error': 'Recurso no encontrado'}), 404
    try:
        return send_from_directory('.', path)
    except:
        return jsonify({'error': 'Archivo no encontrado'}), 404

def run_server():
    """Ejecutar el servidor con manejo robusto de errores"""
    try:
        if not os.path.exists(DB_NAME):
            logger.info("🔧 Creando base de datos...")
            init_db()
        else:
            logger.info("✅ Base de datos existente")
            try:
                conn = get_db()
                conn.execute("PRAGMA integrity_check")
                conn.close()
                logger.info("✅ Integridad de base de datos verificada")
            except Exception as e:
                logger.warning(f"⚠️ Error verificando integridad: {e}")
        
        logger.info("="*50)
        logger.info("🚀 AJHB Backend - Sistema Contable")
        logger.info("="*50)
        logger.info("📡 API disponible en: http://localhost:5000")
        logger.info("🌐 Acceso red local: http://0.0.0.0:5000")
        logger.info("🔗 Health check: http://localhost:5000/api/health")
        logger.info("📝 Logs guardados en: ajhb_backend.log")
        logger.info("🛡️  Modo: 24/7 con auto-recuperación")
        logger.info("="*50)
        
        # Usar servidor de producción con manejo de errores
        from werkzeug.serving import make_server
        
        server = make_server(
            '0.0.0.0', 
            5000, 
            app, 
            threaded=True,
            request_handler=None
        )
        
        logger.info("✅ Servidor iniciado correctamente")
        logger.info("🔄 Esperando conexiones...")
        
        server.serve_forever()
        
    except OSError as e:
        if 'Address already in use' in str(e):
            logger.critical("❌ El puerto 5000 ya está en uso")
            logger.info("💡 Solución: Cierra el otro proceso o cambia el puerto")
        else:
            logger.critical(f"❌ Error de sistema: {e}", exc_info=True)
        raise
    
    except KeyboardInterrupt:
        logger.info("\n🛑 Servidor detenido por el usuario")
    
    except Exception as e:
        logger.critical(f"❌ Error fatal: {e}", exc_info=True)
        raise

if __name__ == '__main__':
    # Intentar iniciar con reintentos
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            run_server()
            break
        except Exception as e:
            if attempt < max_attempts - 1:
                wait_time = (attempt + 1) * 5
                logger.error(f"⚠️ Intento {attempt + 1}/{max_attempts} falló")
                logger.info(f"⏳ Reintentando en {wait_time} segundos...")
                time.sleep(wait_time)
            else:
                logger.critical("❌ No se pudo iniciar el servidor después de varios intentos")
                sys.exit(1)
