from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import hashlib
import secrets
import base64
from datetime import datetime, timedelta
import jwt
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
import logging

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ajhb_auth.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Configuración de seguridad (CAMBIAR EN PRODUCCIÓN)
SECRET_KEY = secrets.token_hex(32)
JWT_SECRET = secrets.token_hex(32)
AES_KEY = secrets.token_bytes(32)  # 256 bits
DB_NAME = 'ajhb_auth.db'

def get_db():
    """Obtener conexión a la base de datos"""
    conn = sqlite3.connect(DB_NAME, timeout=20.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    return conn

def encrypt_data(data: str) -> str:
    """Cifrar datos con AES-256-CBC"""
    try:
        iv = secrets.token_bytes(16)
        cipher = Cipher(algorithms.AES(AES_KEY), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data.encode()) + padder.finalize()
        
        encrypted = encryptor.update(padded_data) + encryptor.finalize()
        result = base64.b64encode(iv + encrypted).decode('utf-8')
        return result
    except Exception as e:
        logger.error(f"Error en cifrado: {e}")
        raise

def decrypt_data(encrypted_data: str) -> str:
    """Descifrar datos con AES-256-CBC"""
    try:
        encrypted_bytes = base64.b64decode(encrypted_data)
        iv = encrypted_bytes[:16]
        encrypted = encrypted_bytes[16:]
        
        cipher = Cipher(algorithms.AES(AES_KEY), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        
        decrypted_padded = decryptor.update(encrypted) + decryptor.finalize()
        
        unpadder = padding.PKCS7(128).unpadder()
        decrypted = unpadder.update(decrypted_padded) + unpadder.finalize()
        
        return decrypted.decode('utf-8')
    except Exception as e:
        logger.error(f"Error en descifrado: {e}")
        raise

def hash_password(password: str, salt: str = None) -> tuple:
    """Hash de contraseña con SHA-256 y salt"""
    if salt is None:
        salt = secrets.token_hex(32)
    
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return base64.b64encode(pwd_hash).decode('utf-8'), salt

def verify_password(password: str, pwd_hash: str, salt: str) -> bool:
    """Verificar contraseña"""
    new_hash, _ = hash_password(password, salt)
    return new_hash == pwd_hash

def generate_token(user_id: int, username: str, role: str) -> str:
    """Generar JWT token"""
    payload = {
        'user_id': user_id,
        'username': username,
        'role': role,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def verify_token(token: str) -> dict:
    """Verificar JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def init_db():
    """Inicializar base de datos"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Tabla de usuarios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            nombre_completo TEXT NOT NULL,
            email TEXT,
            role TEXT NOT NULL,
            permisos TEXT NOT NULL,
            activo INTEGER DEFAULT 1,
            fecha_creacion TEXT NOT NULL,
            ultimo_acceso TEXT,
            creado_por INTEGER
        )
    ''')
    
    # Tabla de sesiones
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sesiones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            fecha_inicio TEXT NOT NULL,
            fecha_expiracion TEXT NOT NULL,
            activa INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES usuarios (id)
        )
    ''')
    
    # Tabla de logs de acceso
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs_acceso (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            accion TEXT NOT NULL,
            ip_address TEXT,
            fecha TEXT NOT NULL,
            exitoso INTEGER DEFAULT 1
        )
    ''')
    
    # Crear usuarios por defecto si no existen
    fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Director Ejecutivo
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE username = 'DirectorEjecutivoAndres'")
    if cursor.fetchone()[0] == 0:
        pwd_hash, salt = hash_password('Hidalgoajhb41')
        cursor.execute('''
            INSERT INTO usuarios (username, password_hash, salt, nombre_completo, 
                                email, role, permisos, fecha_creacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('DirectorEjecutivoAndres', pwd_hash, salt, 'Andrés Hidalgo - Director Ejecutivo', 
              'andres@ajhb.com', 'director', 'all', fecha_actual))
        logger.info("✅ Usuario Director creado - Username: DirectorEjecutivoAndres, Password: Hidalgoajhb41")
    
    # Secretario
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE username = 'Secretariosajhb1a'")
    if cursor.fetchone()[0] == 0:
        pwd_hash, salt = hash_password('Secretosajhb42')
        cursor.execute('''
            INSERT INTO usuarios (username, password_hash, salt, nombre_completo, 
                                email, role, permisos, fecha_creacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('Secretariosajhb1a', pwd_hash, salt, 'Secretario General', 
              'secretario@ajhb.com', 'secretario', 'ventas,secretarios', fecha_actual))
        logger.info("✅ Usuario Secretario creado - Username: Secretariosajhb1a, Password: Secretosajhb42")
    
    conn.commit()
    conn.close()
    logger.info("✅ Base de datos de autenticación inicializada")

# ==================== RUTAS DE AUTENTICACIÓN ====================

@app.route('/api/login', methods=['POST'])
@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login de usuario"""
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Credenciales incompletas'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Buscar usuario
        cursor.execute('SELECT * FROM usuarios WHERE username = ? AND activo = 1', (username,))
        user = cursor.fetchone()
        
        if not user:
            # Log de intento fallido
            log_access(None, username, 'login_fallido', request.remote_addr, False)
            return jsonify({'success': False, 'error': 'Credenciales inválidas'}), 401
        
        # Verificar contraseña
        if not verify_password(password, user['password_hash'], user['salt']):
            log_access(user['id'], username, 'login_fallido', request.remote_addr, False)
            return jsonify({'success': False, 'error': 'Credenciales inválidas'}), 401
        
        # Generar token
        token = generate_token(user['id'], user['username'], user['role'])
        
        # Actualizar último acceso
        fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('UPDATE usuarios SET ultimo_acceso = ? WHERE id = ?', 
                      (fecha_actual, user['id']))
        
        # Crear sesión
        fecha_expiracion = (datetime.now() + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO sesiones (user_id, token, ip_address, user_agent, 
                                fecha_inicio, fecha_expiracion)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user['id'], token, request.remote_addr, request.headers.get('User-Agent'),
              fecha_actual, fecha_expiracion))
        
        conn.commit()
        conn.close()
        
        # Log de acceso exitoso
        log_access(user['id'], username, 'login_exitoso', request.remote_addr, True)
        
        return jsonify({
            'success': True,
            'token': token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'nombre_completo': user['nombre_completo'],
                'role': user['role'],
                'permisos': user['permisos']
            }
        })
        
    except Exception as e:
        logger.error(f"Error en login: {e}")
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

@app.route('/api/verify', methods=['GET', 'POST'])
@app.route('/api/auth/verify', methods=['GET', 'POST'])
def verify():
    """Verificar token"""
    try:
        # Obtener token del header Authorization o del body
        token = None
        auth_header = request.headers.get('Authorization')
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        elif request.json:
            token = request.json.get('token')
        
        if not token:
            return jsonify({'valid': False, 'error': 'Token no proporcionado'}), 400
        
        payload = verify_token(token)
        
        if not payload:
            return jsonify({'valid': False, 'error': 'Token inválido o expirado'}), 401
        
        return jsonify({'valid': True, 'user': payload})
        
    except Exception as e:
        logger.error(f"Error en verificación: {e}")
        return jsonify({'valid': False, 'error': 'Error interno del servidor'}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Logout de usuario"""
    try:
        data = request.json
        token = data.get('token')
        
        if token:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('UPDATE sesiones SET activa = 0 WHERE token = ?', (token,))
            conn.commit()
            conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error en logout: {e}")
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

# ==================== RUTAS DE GESTIÓN DE USUARIOS ====================

@app.route('/api/users', methods=['GET'])
def get_users():
    """Obtener todos los usuarios (solo director)"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        payload = verify_token(token)
        
        if not payload or payload['role'] != 'director':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, nombre_completo, email, role, permisos, 
                   activo, fecha_creacion, ultimo_acceso 
            FROM usuarios 
            ORDER BY fecha_creacion DESC
        ''')
        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({'success': True, 'data': users})
        
    except Exception as e:
        logger.error(f"Error al obtener usuarios: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/users', methods=['POST'])
def create_user():
    """Crear nuevo usuario (solo director)"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        payload = verify_token(token)
        
        if not payload or payload['role'] != 'director':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        data = request.json
        username = data.get('username')
        password = data.get('password')
        nombre_completo = data.get('nombre_completo')
        email = data.get('email')
        role = data.get('role')
        permisos = data.get('permisos')
        
        if not all([username, password, nombre_completo, role, permisos]):
            return jsonify({'success': False, 'error': 'Datos incompletos'}), 400
        
        # Hash de contraseña
        pwd_hash, salt = hash_password(password)
        
        conn = get_db()
        cursor = conn.cursor()
        fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT INTO usuarios (username, password_hash, salt, nombre_completo, 
                                email, role, permisos, fecha_creacion, creado_por)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (username, pwd_hash, salt, nombre_completo, email, role, permisos, 
              fecha_actual, payload['user_id']))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Usuario creado: {username} ({role})")
        return jsonify({'success': True, 'id': user_id})
        
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'El usuario ya existe'}), 400
    except Exception as e:
        logger.error(f"Error al crear usuario: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """Actualizar usuario (solo director)"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        payload = verify_token(token)
        
        if not payload or payload['role'] != 'director':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        data = request.json
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Construir query dinámicamente
        updates = []
        params = []
        
        if 'nombre_completo' in data:
            updates.append('nombre_completo = ?')
            params.append(data['nombre_completo'])
        
        if 'email' in data:
            updates.append('email = ?')
            params.append(data['email'])
        
        if 'role' in data:
            updates.append('role = ?')
            params.append(data['role'])
        
        if 'permisos' in data:
            updates.append('permisos = ?')
            params.append(data['permisos'])
        
        if 'activo' in data:
            updates.append('activo = ?')
            params.append(data['activo'])
        
        if 'password' in data:
            pwd_hash, salt = hash_password(data['password'])
            updates.append('password_hash = ?')
            updates.append('salt = ?')
            params.extend([pwd_hash, salt])
        
        if updates:
            params.append(user_id)
            query = f"UPDATE usuarios SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
        
        conn.close()
        
        logger.info(f"✅ Usuario actualizado: ID {user_id}")
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error al actualizar usuario: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Eliminar usuario (solo director)"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        payload = verify_token(token)
        if not payload or payload['role'] != 'director':
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        # No permitir eliminar al director
        if user_id == 1:
            return jsonify({'success': False, 'error': 'No se puede eliminar al director'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE usuarios SET activo = 0 WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Usuario desactivado: ID {user_id}")
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error al eliminar usuario: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def log_access(user_id, username, accion, ip_address, exitoso):
    """Registrar acceso en logs"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO logs_acceso (user_id, username, accion, ip_address, fecha, exitoso)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, username, accion, ip_address, fecha_actual, 1 if exitoso else 0))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error al registrar log: {e}")

# ==================== RUTAS ESTÁTICAS ====================

@app.route('/')
def index():
    return send_from_directory('.', 'login1.html')

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'service': 'auth'})

# ==================== INICIALIZACIÓN ====================

if __name__ == '__main__':
    init_db()
    logger.info("🔐 Iniciando servidor de autenticación en puerto 5003...")
    app.run(host='0.0.0.0', port=5003, debug=True)
