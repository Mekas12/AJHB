from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import sqlite3
import json
from datetime import datetime
import os
import logging
import mimetypes

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ajhb_secretarios.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Configuración de archivos
UPLOAD_FOLDER = 'uploads_secretarios'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'rar'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Configuración de la base de datos
DB_NAME = 'ajhb_secretarios.db'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    """Obtener conexión a la base de datos"""
    conn = sqlite3.connect(DB_NAME, timeout=20.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    return conn

def init_db():
    """Inicializar base de datos con tablas necesarias"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Migración: Agregar columna etiquetas si no existe
    try:
        cursor.execute("SELECT etiquetas FROM documentos LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("🔧 Agregando columna 'etiquetas' a tabla documentos...")
        cursor.execute("ALTER TABLE documentos ADD COLUMN etiquetas TEXT")
        conn.commit()
        logger.info("✅ Columna 'etiquetas' agregada exitosamente")
    
    # Tabla de Notas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            contenido TEXT NOT NULL,
            categoria TEXT DEFAULT 'general',
            prioridad TEXT DEFAULT 'media',
            color TEXT DEFAULT '#C9A96E',
            fecha_creacion TEXT NOT NULL,
            fecha_modificacion TEXT NOT NULL,
            archivada INTEGER DEFAULT 0,
            etiquetas TEXT
        )
    ''')
    
    # Tabla de Recordatorios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recordatorios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descripcion TEXT,
            fecha_recordatorio TEXT NOT NULL,
            hora_recordatorio TEXT NOT NULL,
            tipo TEXT DEFAULT 'general',
            completado INTEGER DEFAULT 0,
            notificado INTEGER DEFAULT 0,
            fecha_creacion TEXT NOT NULL
        )
    ''')
    
    # Tabla de Eventos del Calendario
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descripcion TEXT,
            fecha_inicio TEXT NOT NULL,
            fecha_fin TEXT NOT NULL,
            hora_inicio TEXT NOT NULL,
            hora_fin TEXT NOT NULL,
            ubicacion TEXT,
            tipo TEXT DEFAULT 'reunion',
            color TEXT DEFAULT '#C9A96E',
            participantes TEXT,
            recordatorio INTEGER DEFAULT 0,
            fecha_creacion TEXT NOT NULL
        )
    ''')
    
    # Tabla de Documentos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            categoria TEXT DEFAULT 'general',
            ruta_archivo TEXT,
            tamano INTEGER,
            tipo_archivo TEXT,
            fecha_subida TEXT NOT NULL,
            subido_por TEXT,
            etiquetas TEXT
        )
    ''')
    
    # Tabla de Tareas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tareas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descripcion TEXT,
            prioridad TEXT DEFAULT 'media',
            estado TEXT DEFAULT 'pendiente',
            fecha_vencimiento TEXT,
            asignado_a TEXT,
            fecha_creacion TEXT NOT NULL,
            fecha_completado TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Base de datos inicializada correctamente")

# ==================== RUTAS DE NOTAS ====================

@app.route('/api/notas', methods=['GET'])
def get_notas():
    """Obtener todas las notas"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM notas ORDER BY fecha_modificacion DESC')
        notas = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({'success': True, 'data': notas})
    except Exception as e:
        logger.error(f"Error al obtener notas: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/notas', methods=['POST'])
def create_nota():
    """Crear una nueva nota"""
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT INTO notas (titulo, contenido, categoria, prioridad, color, 
                             fecha_creacion, fecha_modificacion, etiquetas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('titulo'),
            data.get('contenido'),
            data.get('categoria', 'general'),
            data.get('prioridad', 'media'),
            data.get('color', '#C9A96E'),
            fecha_actual,
            fecha_actual,
            json.dumps(data.get('etiquetas', []))
        ))
        
        conn.commit()
        nota_id = cursor.lastrowid
        conn.close()
        
        return jsonify({'success': True, 'id': nota_id})
    except Exception as e:
        logger.error(f"Error al crear nota: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/notas/<int:nota_id>', methods=['PUT'])
def update_nota(nota_id):
    """Actualizar una nota"""
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            UPDATE notas 
            SET titulo = ?, contenido = ?, categoria = ?, prioridad = ?, 
                color = ?, fecha_modificacion = ?, etiquetas = ?
            WHERE id = ?
        ''', (
            data.get('titulo'),
            data.get('contenido'),
            data.get('categoria'),
            data.get('prioridad'),
            data.get('color'),
            fecha_actual,
            json.dumps(data.get('etiquetas', [])),
            nota_id
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error al actualizar nota: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/notas/<int:nota_id>', methods=['DELETE'])
def delete_nota(nota_id):
    """Eliminar una nota"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM notas WHERE id = ?', (nota_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error al eliminar nota: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== RUTAS DE RECORDATORIOS ====================

@app.route('/api/recordatorios', methods=['GET'])
def get_recordatorios():
    """Obtener todos los recordatorios"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM recordatorios ORDER BY fecha_recordatorio, hora_recordatorio')
        recordatorios = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({'success': True, 'data': recordatorios})
    except Exception as e:
        logger.error(f"Error al obtener recordatorios: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recordatorios', methods=['POST'])
def create_recordatorio():
    """Crear un nuevo recordatorio"""
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT INTO recordatorios (titulo, descripcion, fecha_recordatorio, 
                                     hora_recordatorio, tipo, fecha_creacion)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            data.get('titulo'),
            data.get('descripcion'),
            data.get('fecha_recordatorio'),
            data.get('hora_recordatorio'),
            data.get('tipo', 'general'),
            fecha_actual
        ))
        
        conn.commit()
        recordatorio_id = cursor.lastrowid
        conn.close()
        
        return jsonify({'success': True, 'id': recordatorio_id})
    except Exception as e:
        logger.error(f"Error al crear recordatorio: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recordatorios/<int:recordatorio_id>/completar', methods=['PUT'])
def completar_recordatorio(recordatorio_id):
    """Marcar recordatorio como completado"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE recordatorios SET completado = 1 WHERE id = ?', (recordatorio_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error al completar recordatorio: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recordatorios/<int:recordatorio_id>', methods=['DELETE'])
def delete_recordatorio(recordatorio_id):
    """Eliminar un recordatorio"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM recordatorios WHERE id = ?', (recordatorio_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error al eliminar recordatorio: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== RUTAS DE EVENTOS ====================

@app.route('/api/eventos', methods=['GET'])
def get_eventos():
    """Obtener todos los eventos"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM eventos ORDER BY fecha_inicio, hora_inicio')
        eventos = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({'success': True, 'data': eventos})
    except Exception as e:
        logger.error(f"Error al obtener eventos: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/eventos', methods=['POST'])
def create_evento():
    """Crear un nuevo evento"""
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT INTO eventos (titulo, descripcion, fecha_inicio, fecha_fin, 
                               hora_inicio, hora_fin, ubicacion, tipo, color, 
                               participantes, recordatorio, fecha_creacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('titulo'),
            data.get('descripcion'),
            data.get('fecha_inicio'),
            data.get('fecha_fin'),
            data.get('hora_inicio'),
            data.get('hora_fin'),
            data.get('ubicacion'),
            data.get('tipo', 'reunion'),
            data.get('color', '#C9A96E'),
            json.dumps(data.get('participantes', [])),
            data.get('recordatorio', 0),
            fecha_actual
        ))
        
        conn.commit()
        evento_id = cursor.lastrowid
        conn.close()
        
        return jsonify({'success': True, 'id': evento_id})
    except Exception as e:
        logger.error(f"Error al crear evento: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/eventos/<int:evento_id>', methods=['DELETE'])
def delete_evento(evento_id):
    """Eliminar un evento"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM eventos WHERE id = ?', (evento_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error al eliminar evento: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== RUTAS DE TAREAS ====================

@app.route('/api/tareas', methods=['GET'])
def get_tareas():
    """Obtener todas las tareas"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tareas ORDER BY fecha_vencimiento')
        tareas = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({'success': True, 'data': tareas})
    except Exception as e:
        logger.error(f"Error al obtener tareas: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tareas', methods=['POST'])
def create_tarea():
    """Crear una nueva tarea"""
    try:
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        
        fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT INTO tareas (titulo, descripcion, prioridad, estado, 
                              fecha_vencimiento, asignado_a, fecha_creacion)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('titulo'),
            data.get('descripcion'),
            data.get('prioridad', 'media'),
            data.get('estado', 'pendiente'),
            data.get('fecha_vencimiento'),
            data.get('asignado_a'),
            fecha_actual
        ))
        
        conn.commit()
        tarea_id = cursor.lastrowid
        conn.close()
        
        return jsonify({'success': True, 'id': tarea_id})
    except Exception as e:
        logger.error(f"Error al crear tarea: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tareas/<int:tarea_id>/completar', methods=['PUT'])
def completar_tarea(tarea_id):
    """Marcar tarea como completada"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            UPDATE tareas 
            SET estado = 'completada', fecha_completado = ? 
            WHERE id = ?
        ''', (fecha_actual, tarea_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error al completar tarea: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== RUTAS DE ARCHIVOS ====================

@app.route('/api/documentos', methods=['GET'])
def get_documentos():
    """Obtener todos los documentos"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM documentos ORDER BY fecha_subida DESC')
        documentos = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({'success': True, 'data': documentos})
    except Exception as e:
        logger.error(f"Error al obtener documentos: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/documentos/upload', methods=['POST'])
def upload_documento():
    """Subir un nuevo documento"""
    try:
        logger.info("📤 Recibiendo solicitud de subida de archivo...")
        
        if 'file' not in request.files:
            logger.error("❌ No se encontró 'file' en request.files")
            return jsonify({'success': False, 'error': 'No se envió ningún archivo'}), 400
        
        file = request.files['file']
        logger.info(f"📄 Archivo recibido: {file.filename}")
        
        if file.filename == '':
            logger.error("❌ Nombre de archivo vacío")
            return jsonify({'success': False, 'error': 'Nombre de archivo vacío'}), 400
        
        if not allowed_file(file.filename):
            logger.error(f"❌ Tipo de archivo no permitido: {file.filename}")
            return jsonify({'success': False, 'error': 'Tipo de archivo no permitido'}), 400
        
        # Guardar archivo
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        
        # Obtener información del archivo
        file_size = os.path.getsize(filepath)
        file_ext = filename.rsplit('.', 1)[1].lower()
        
        # Guardar en base de datos
        conn = get_db()
        cursor = conn.cursor()
        fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT INTO documentos (nombre, descripcion, categoria, ruta_archivo, 
                                  tamano, tipo_archivo, fecha_subida, subido_por, etiquetas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            filename,
            request.form.get('descripcion', ''),
            request.form.get('categoria', 'general'),
            unique_filename,
            file_size,
            file_ext,
            fecha_actual,
            request.form.get('subido_por', 'Usuario'),
            request.form.get('etiquetas', '')
        ))
        
        conn.commit()
        documento_id = cursor.lastrowid
        conn.close()
        
        logger.info(f"✅ Documento guardado exitosamente: ID={documento_id}, Archivo={unique_filename}")
        return jsonify({'success': True, 'id': documento_id, 'filename': unique_filename})
    except Exception as e:
        logger.error(f"❌ Error al subir documento: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/documentos/<int:documento_id>/download', methods=['GET'])
def download_documento(documento_id):
    """Descargar un documento"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM documentos WHERE id = ?', (documento_id,))
        documento = cursor.fetchone()
        conn.close()
        
        if not documento:
            return jsonify({'success': False, 'error': 'Documento no encontrado'}), 404
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], documento['ruta_archivo'])
        
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'Archivo no encontrado en el servidor'}), 404
        
        return send_file(filepath, as_attachment=True, download_name=documento['nombre'])
    except Exception as e:
        logger.error(f"Error al descargar documento: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/documentos/<int:documento_id>', methods=['DELETE'])
def delete_documento(documento_id):
    """Eliminar un documento"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM documentos WHERE id = ?', (documento_id,))
        documento = cursor.fetchone()
        
        if documento:
            # Eliminar archivo físico
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], documento['ruta_archivo'])
            if os.path.exists(filepath):
                os.remove(filepath)
            
            # Eliminar de base de datos
            cursor.execute('DELETE FROM documentos WHERE id = ?', (documento_id,))
            conn.commit()
        
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error al eliminar documento: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/documentos/search', methods=['GET'])
def search_documentos():
    """Buscar documentos por nombre o categoría"""
    try:
        query = request.args.get('q', '')
        categoria = request.args.get('categoria', '')
        
        conn = get_db()
        cursor = conn.cursor()
        
        sql = 'SELECT * FROM documentos WHERE 1=1'
        params = []
        
        if query:
            sql += ' AND (nombre LIKE ? OR descripcion LIKE ? OR etiquetas LIKE ?)'
            params.extend([f'%{query}%', f'%{query}%', f'%{query}%'])
        
        if categoria:
            sql += ' AND categoria = ?'
            params.append(categoria)
        
        sql += ' ORDER BY fecha_subida DESC'
        
        cursor.execute(sql, params)
        documentos = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({'success': True, 'data': documentos})
    except Exception as e:
        logger.error(f"Error al buscar documentos: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== RUTAS ESTÁTICAS ====================

@app.route('/')
def index():
    """Servir página principal de Secretarios"""
    return send_from_directory('.', 'Secretarios.html')

@app.route('/<path:path>')
def serve_static(path):
    """Servir archivos estáticos"""
    if path.startswith('api/'):
        return jsonify({'error': 'Recurso no encontrado'}), 404
    try:
        return send_from_directory('.', path)
    except:
        return jsonify({'error': 'Archivo no encontrado'}), 404

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'service': 'secretarios'})

# ==================== INICIALIZACIÓN ====================

if __name__ == '__main__':
    init_db()
    logger.info("🗂️ Iniciando servidor de Secretarios en puerto 5002...")
    app.run(host='0.0.0.0', port=5002, debug=True)
