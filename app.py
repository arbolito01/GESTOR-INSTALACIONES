from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import os
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import date, datetime
import json
from routeros_api import RouterOsApiPool
import requests

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'

# --- Configuración de la Base de Datos ---
db_config = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '',
    'database': 'gestor_instalaciones'
}

# --- Configuración de Archivos ---
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- Funciones Auxiliares ---
def get_db_connection():
    return mysql.connector.connect(**db_config)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Decoradores para Control de Acceso ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'id_usuario' not in session:
            flash("Debes iniciar sesión para acceder a esta página.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'id_usuario' not in session or not session.get('es_admin'):
            flash("No tienes permisos para acceder a esta página.", "error")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def instalador_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'id_usuario' not in session or session.get('es_admin'):
            flash("No tienes permisos para acceder a esta página.", "error")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# --- Rutas de Autenticación ---
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        try:
            conexion = get_db_connection()
            cursor = conexion.cursor()
            sql = "INSERT INTO usuarios (nombre, email, password, es_admin) VALUES (%s, %s, %s, 0)"
            valores = (nombre, email, hashed_password)
            cursor.execute(sql, valores)
            conexion.commit()
            flash("Registro exitoso. ¡Inicia sesión ahora!", "success")
            return redirect(url_for('login'))
        except mysql.connector.Error as err:
            flash(f"Error al registrar usuario: {err}", "error")
            return redirect(url_for('registro'))
        finally:
            if 'conexion' in locals() and conexion.is_connected():
                cursor.close()
                conexion.close()
    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conexion = get_db_connection()
        cursor = conexion.cursor(dictionary=True)
        sql = "SELECT * FROM usuarios WHERE email = %s"
        cursor.execute(sql, (email,))
        usuario = cursor.fetchone()
        cursor.close()
        conexion.close()

        if usuario and check_password_hash(usuario['password'], password):
            session['id_usuario'] = usuario['id_usuario']
            session['nombre'] = usuario['nombre']
            session['es_admin'] = usuario['es_admin']
            flash(f"¡Bienvenido, {usuario['nombre']}!", "success")
            return redirect(url_for('index'))
        else:
            flash('Credenciales incorrectas.', "error")
            return render_template('login.html')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.pop('id_usuario', None)
    session.pop('nombre', None)
    session.pop('es_admin', None) 
    flash("Has cerrado sesión correctamente.", "success")
    return redirect(url_for('login'))

# --- Rutas del Panel de Administración ---
@app.route('/admin')
@admin_required
def admin():
    conexion = get_db_connection()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM instalaciones")
    instalaciones = cursor.fetchall()
    cursor.execute("SELECT r.*, u.nombre AS nombre_usuario, i.nombre AS nombre_instalacion FROM reservas r JOIN usuarios u ON r.id_usuario = u.id_usuario JOIN instalaciones i ON r.id_instalacion = i.id_instalacion ORDER BY r.fecha DESC")
    reservas = cursor.fetchall()
    cursor.execute("SELECT * FROM usuarios")
    usuarios = cursor.fetchall()
    cursor.execute("""
        SELECT t.*, i.nombre AS nombre_instalacion, u.nombre AS nombre_usuario_asignado, a.nombre AS nombre_admin
        FROM tareas t
        JOIN instalaciones i ON t.id_instalacion = i.id_instalacion
        JOIN usuarios u ON t.id_usuario_asignado = u.id_usuario
        JOIN usuarios a ON t.id_admin = a.id_usuario
        ORDER BY t.fecha_asignacion DESC
    """)
    tareas = cursor.fetchall()
    # Nuevo: Obtener la lista de técnicos/instaladores (usuarios no admin)
    cursor.execute("SELECT id_usuario, nombre FROM usuarios WHERE es_admin = 0")
    tecnicos = cursor.fetchall()
    cursor.close()
    conexion.close()

    return render_template('admin.html', instalaciones=instalaciones, reservas=reservas, usuarios=usuarios, tareas=tareas, tecnicos=tecnicos)

@app.route('/nueva-instalacion', methods=['GET', 'POST'])
@login_required
@admin_required
def nueva_instalacion():
    conexion = get_db_connection()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT id_usuario, nombre FROM usuarios WHERE es_admin = 0")
    tecnicos = cursor.fetchall()
    
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')
        estado = request.form.get('estado')
        hora_solicitada = request.form.get('hora_solicitada')
        codigo_cliente = request.form.get('codigo_cliente')
        solicitud = request.form.get('solicitud')
        tecnico_asignado_id = request.form.get('tecnico_asignado')
        nombre_cliente = request.form.get('nombre_cliente')
        telefono_cliente = request.form.get('telefono_cliente')
        referencia = request.form.get('referencia')
        ruta_caja_nap = request.form.get('ruta_caja_nap')
        latitud = request.form.get('latitud', '')
        longitud = request.form.get('longitud', '')
        ubicacion_gps = f"{latitud},{longitud}" if latitud and longitud else ""
        
        imagen_url = ""
        if 'imagen' in request.files and request.files['imagen'].filename != '':
            file = request.files['imagen']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(full_path)
                imagen_url = os.path.join('uploads', filename).replace('\\', '/')
        
        try:
            nombre_tecnico = None
            if tecnico_asignado_id:
                cursor.execute("SELECT nombre FROM usuarios WHERE id_usuario = %s", (tecnico_asignado_id,))
                result = cursor.fetchone()
                if result:
                    nombre_tecnico = result['nombre']
            
            sql = "INSERT INTO instalaciones (nombre, descripcion, estado, imagen_url, hora_solicitada, codigo_cliente, solicitud, id_instalador, tecnico_asignado, nombre_cliente, telefono_cliente, referencia, ruta_caja_nap, ubicacion_gps) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            valores = (nombre, descripcion, estado, imagen_url, hora_solicitada, codigo_cliente, solicitud, tecnico_asignado_id, nombre_tecnico, nombre_cliente, telefono_cliente, referencia, ruta_caja_nap, ubicacion_gps)
            cursor.execute(sql, valores)
            id_instalacion_creada = cursor.lastrowid
            
            if tecnico_asignado_id:
                estado_tarea = "Pendiente"
                fecha_asignacion = date.today()
                id_admin = session.get('id_usuario')
                descripcion_tarea = f"Instalación de {solicitud} para el cliente {nombre_cliente}"
                
                sql_insert_tarea = "INSERT INTO tareas (id_instalacion, id_admin, id_usuario_asignado, tipo_tarea, descripcion, fecha_asignacion, estado) VALUES (%s, %s, %s, %s, %s, %s, %s)"
                valores_tarea = (id_instalacion_creada, id_admin, tecnico_asignado_id, solicitud, descripcion_tarea, fecha_asignacion, estado_tarea)
                cursor.execute(sql_insert_tarea, valores_tarea)
            
            conexion.commit()
            flash("Instalación/Solicitud añadida con éxito.", "success")
            return redirect(url_for('admin'))
        except mysql.connector.Error as err:
            flash(f"Error al añadir la instalación/solicitud: {err}", "error")
        finally:
            cursor.close()
            conexion.close()
            return render_template('nueva_instalacion.html')
    
    maps_api_key = 'TU_API_KEY_AQUI'
    cursor.close()
    conexion.close()
    return render_template('nueva_instalacion.html', tecnicos=tecnicos, maps_api_key=maps_api_key)

@app.route('/editar_instalacion/<int:id>', methods=['GET', 'POST'])
@admin_required
def editar_instalacion(id):
    conexion = get_db_connection()
    cursor = conexion.cursor(dictionary=True)
    
    if request.method == 'POST':
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        estado = request.form['estado']
        imagen_url = request.form.get('imagen_actual', '')
        
        if 'imagen' in request.files and request.files['imagen'].filename != '':
            file = request.files['imagen']
            if file and allowed_file(file.filename):
                if imagen_url and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(imagen_url))):
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(imagen_url)))
                
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                imagen_url = os.path.join('uploads', filename).replace('\\', '/')
        
        cursor.execute("UPDATE instalaciones SET nombre = %s, descripcion = %s, estado = %s, imagen_url = %s WHERE id_instalacion = %s", (nombre, descripcion, estado, imagen_url, id))
        conexion.commit()
        conexion.close()
        flash("Instalación actualizada con éxito.", "success")
        return redirect(url_for('admin'))

    cursor.execute("SELECT * FROM instalaciones WHERE id_instalacion = %s", (id,))
    instalacion = cursor.fetchone()
    conexion.close()
    if not instalacion:
        flash("Instalación no encontrada.", "error")
        return redirect(url_for('admin'))
        
    return render_template('editar_instalacion.html', instalacion=instalacion)

@app.route('/eliminar_instalacion/<int:id>', methods=['POST'])
@admin_required
def eliminar_instalacion(id):
    try:
        conexion = get_db_connection()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT imagen_url FROM instalaciones WHERE id_instalacion = %s", (id,))
        instalacion = cursor.fetchone()
        if instalacion and instalacion['imagen_url'] and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(instalacion['imagen_url']))):
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(instalacion['imagen_url'])))
        cursor.execute("DELETE FROM reservas WHERE id_instalacion = %s", (id,))
        cursor.execute("DELETE FROM tareas WHERE id_instalacion = %s", (id,))
        cursor.execute("DELETE FROM instalaciones WHERE id_instalacion = %s", (id,))
        conexion.commit()
        flash("Instalación eliminada con éxito.", "success")
        return redirect(url_for('admin'))
    except mysql.connector.Error as err:
        flash(f"Error al eliminar la instalación: {err}", "error")
        return redirect(url_for('admin'))
    finally:
        if 'conexion' in locals() and conexion.is_connected():
            cursor.close()
            conexion.close()

@app.route('/editar_usuario/<int:id>', methods=['GET', 'POST'])
@admin_required
def editar_usuario(id):
    conexion = get_db_connection()
    cursor = conexion.cursor(dictionary=True)
    usuario = None
    try:
        cursor.execute("SELECT * FROM usuarios WHERE id_usuario = %s", (id,))
        usuario = cursor.fetchone()
        if not usuario:
            flash("Usuario no encontrado.", "error")
            return redirect(url_for('admin'))

        if request.method == 'POST':
            nombre = request.form['nombre']
            email = request.form['email']
            password = request.form['password']
            
            sql_update = "UPDATE usuarios SET nombre = %s, email = %s WHERE id_usuario = %s"
            valores = (nombre, email, id)

            if password:
                hashed_password = generate_password_hash(password)
                sql_update = "UPDATE usuarios SET nombre = %s, email = %s, password = %s WHERE id_usuario = %s"
                valores = (nombre, email, hashed_password, id)
            
            cursor.execute(sql_update, valores)
            conexion.commit()
            flash('Usuario actualizado con éxito', 'success')
            return redirect(url_for('admin'))
    except mysql.connector.Error as err:
        flash(f"Error al editar el usuario: {err}", "error")
        return redirect(url_for('admin'))
    finally:
        if 'conexion' in locals() and conexion.is_connected():
            cursor.close()
            conexion.close()
    
    return render_template('editar_usuario.html', usuario=usuario)

@app.route('/eliminar_usuario/<int:id>', methods=['POST'])
@admin_required
def eliminar_usuario(id):
    if id == session['id_usuario']:
        flash("No puedes eliminar tu propio usuario.", "error")
        return redirect(url_for('admin'))
        
    try:
        conexion = get_db_connection()
        cursor = conexion.cursor()
        cursor.execute("DELETE FROM tareas WHERE id_usuario_asignado = %s", (id,))
        cursor.execute("DELETE FROM usuarios WHERE id_usuario = %s", (id,))
        conexion.commit()
        flash("Usuario eliminado con éxito.", "success")
    except mysql.connector.Error as err:
        flash(f"Error al eliminar el usuario: {err}", "error")
    finally:
        if 'conexion' in locals() and conexion.is_connected():
            cursor.close()
            conexion.close()
    
    return redirect(url_for('admin'))

@app.route('/toggle_admin/<int:id>', methods=['POST'])
@admin_required
def toggle_admin(id):
    try:
        conexion = get_db_connection()
        cursor = conexion.cursor()
        cursor.execute("SELECT es_admin FROM usuarios WHERE id_usuario = %s", (id,))
        usuario = cursor.fetchone()
        if usuario:
            es_admin_actual = usuario[0]
            nuevo_estado = not es_admin_actual
            sql = "UPDATE usuarios SET es_admin = %s WHERE id_usuario = %s"
            cursor.execute(sql, (nuevo_estado, id))
            conexion.commit()
            flash("Permisos de administrador actualizados con éxito.", "success")
        else:
            flash("Usuario no encontrado.", "error")
    except mysql.connector.Error as err:
        flash(f"Error al actualizar permisos: {err}", "error")
    finally:
        if 'conexion' in locals() and conexion.is_connected():
            cursor.close()
            conexion.close()
    return redirect(url_for('admin'))

@app.route('/asignar_tarea', methods=['GET', 'POST'])
@admin_required
def asignar_tarea():
    conexion = get_db_connection()
    cursor = conexion.cursor(dictionary=True)
    if request.method == 'POST':
        id_instalacion = request.form['id_instalacion']
        id_usuario_asignado = request.form['id_usuario_asignado']
        tipo_tarea = request.form['tipo_tarea']
        descripcion = request.form['descripcion']
        fecha_asignacion = date.today()
        id_admin = session['id_usuario']
        estado = "Pendiente"
        try:
            cursor.execute("SELECT nombre FROM usuarios WHERE id_usuario = %s", (id_usuario_asignado,))
            nombre_tecnico = cursor.fetchone()['nombre']
            sql_insert_tarea = "INSERT INTO tareas (id_instalacion, id_admin, id_usuario_asignado, tipo_tarea, descripcion, fecha_asignacion, estado) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            valores_tarea = (id_instalacion, id_admin, id_usuario_asignado, tipo_tarea, descripcion, fecha_asignacion, estado)
            cursor.execute(sql_insert_tarea, valores_tarea)
            sql_update_instalacion = "UPDATE instalaciones SET tecnico_asignado = %s, estado = %s, id_instalador = %s WHERE id_instalacion = %s"
            valores_update = (nombre_tecnico, 'Asignado', id_usuario_asignado, id_instalacion)
            cursor.execute(sql_update_instalacion, valores_update)
            conexion.commit()
            flash("Tarea asignada con éxito.", "success")
            return redirect(url_for('admin'))
        except mysql.connector.Error as err:
            flash(f"Error al asignar la tarea: {err}", "error")
        finally:
            if 'conexion' in locals() and conexion.is_connected():
                cursor.close()
                conexion.close()
    
    cursor.execute("SELECT id_instalacion, nombre FROM instalaciones WHERE estado = 'Pendiente'")
    instalaciones = cursor.fetchall()
    cursor.execute("SELECT id_usuario, nombre FROM usuarios WHERE es_admin = 0")
    usuarios_no_admin = cursor.fetchall()
    cursor.close()
    conexion.close()
    return render_template('asignar_tarea.html', instalaciones=instalaciones, usuarios_no_admin=usuarios_no_admin)

# --- Rutas de Instalador ---
@app.route('/')
@login_required
def index():
    es_admin = session.get('es_admin', False)
    if es_admin:
        return redirect(url_for('admin'))
    
    id_usuario = session.get('id_usuario')
    conexion = get_db_connection()
    cursor = conexion.cursor(dictionary=True)
    sql = "SELECT * FROM instalaciones WHERE id_instalador = %s AND estado != 'Completado'"
    cursor.execute(sql, (id_usuario,))
    tareas_asignadas = cursor.fetchall()
    cursor.close()
    conexion.close()
    
    return render_template('tareas_asignadas.html', tareas=tareas_asignadas)

@app.route('/mis_tareas')
@login_required
@instalador_required
def mis_tareas():
    id_usuario = session['id_usuario']
    conexion = get_db_connection()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("""
        SELECT t.*, i.nombre AS nombre_instalacion
        FROM tareas t
        JOIN instalaciones i ON t.id_instalacion = i.id_instalacion
        WHERE t.id_usuario_asignado = %s
        ORDER BY t.fecha_asignacion DESC
    """, (id_usuario,))
    mis_tareas = cursor.fetchall()
    cursor.close()
    conexion.close()
    return render_template('mis_tareas.html', mis_tareas=mis_tareas)

@app.route('/completar_instalacion/<int:instalacion_id>', methods=['GET', 'POST'])
@login_required
@instalador_required
def completar_instalacion(instalacion_id):
    conexion = get_db_connection()
    cursor = conexion.cursor(dictionary=True)
    sql_instalacion = "SELECT * FROM instalaciones WHERE id_instalacion = %s AND id_instalador = %s"
    cursor.execute(sql_instalacion, (instalacion_id, session.get('id_usuario')))
    instalacion = cursor.fetchone()
    if not instalacion:
        flash("La instalación no existe o no te ha sido asignada.", "error")
        cursor.close()
        conexion.close()
        return redirect(url_for('index'))
    if request.method == 'POST':
        try:
            # Obtener todos los datos del nuevo formulario
            referencia = request.form.get('referencia')
            numero_serie = request.form.get('numero_serie')
            metodo_pago = request.form.get('metodo_pago')
            numero_transaccion = request.form.get('numero_transaccion')
            descripcion_final = request.form.get('descripcion_final')
            
            # Obtener la ubicación GPS del nuevo formulario
            latitud = request.form.get('latitud')
            longitud = request.form.get('longitud')
            ubicacion_gps_final = f"{latitud},{longitud}"
            
            # Validar campos obligatorios
            if not latitud or not longitud:
                flash("La ubicación GPS es obligatoria.", "error")
                return redirect(url_for('completar_instalacion', instalacion_id=instalacion_id))

            # Manejar la subida de la foto
            foto = request.files.get('foto')
            foto_url = ""
            if foto and allowed_file(foto.filename):
                filename = secure_filename(foto.filename)
                foto_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                foto.save(foto_path)
                foto_url = os.path.join('uploads', filename).replace('\\', '/')
            else:
                flash("Debes adjuntar una foto de la instalación.", "error")
                return redirect(url_for('completar_instalacion', instalacion_id=instalacion_id))

            fecha_completado = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Actualizar la tabla de instalaciones con todos los nuevos datos
            sql_update = """
                UPDATE instalaciones SET 
                estado = 'Completado', 
                descripcion_final = %s, 
                ubicacion_gps_final = %s, 
                foto_adjunta = %s, 
                fecha_completado = %s,
                referencia = %s,
                numero_serie = %s,
                metodo_pago = %s,
                numero_transaccion = %s
                WHERE id_instalacion = %s
            """
            valores_update = (
                descripcion_final, ubicacion_gps_final, foto_url, fecha_completado,
                referencia, numero_serie, metodo_pago, numero_transaccion,
                instalacion_id
            )
            cursor.execute(sql_update, valores_update)

            # Actualizar el estado de la tarea en la tabla de tareas
            sql_update_tarea = "UPDATE tareas SET estado = 'Completada' WHERE id_instalacion = %s AND id_usuario_asignado = %s"
            cursor.execute(sql_update_tarea, (instalacion_id, session.get('id_usuario')))
            
            conexion.commit()
    # --- Lógica de la API de WhatsApp ---instalacion['51905433166']
            whatsapp_token = "EAAPXjpwVm2QBPJEJZCF5iiiIdcgT1ZBgg2jUSWC6Cr9C1QqmVxFLZBDHHOI9riLF9UZAxjhOZBsNNfeKWUjB9FDGZCMM1J0R2iuoueF4FwafZAPWiyMRUIJ1mPT8uZCMtzkdKirqua2SbxnpcbM57HajnJKI2szfRZAMtPhigsdKVuJ9gvJayAGJkoThqF2eA8oSdcLiRhI1pwAKNhVx5ZBpquw3iYXgMNZBtKoCLnTtSNg2VO46gZDZD" # Reemplaza con tu token
            phone_number_id = "738682315995138" # Reemplaza con tu ID de teléfono
            recipient_number = "51905433166"
            message_text = f"¡Hola! Tu instalación de {instalacion['nombre']} ha sido completada con éxito. Fecha de finalización: {fecha_completado}."
            headers = {
                "Authorization": f"Bearer {whatsapp_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "messaging_product": "whatsapp",
                "to": recipient_number,
                "type": "text",
                "text": {
                    "body": message_text
                }
            }
            try:
                response = requests.post(
                    f"https://graph.facebook.com/v15.0/{phone_number_id}/messages",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                print("Mensaje de WhatsApp enviado con éxito.")
            except requests.exceptions.RequestException as e:
                print(f"Error al enviar el mensaje de WhatsApp: {e}")
            # --- Fin de la lógica de la API de WhatsApp ---


            flash('La tarea se ha completado con éxito.', "success")
            return redirect(url_for('mis_tareas_completadas'))
        except Exception as e:
            flash(f'Error al completar la tarea: {e}', "error")
            # Esto imprimirá el error en la consola para depuración
            print(f"Error en completar_instalacion: {e}")
            return redirect(url_for('completar_instalacion', instalacion_id=instalacion_id))
        finally:
            if 'conexion' in locals() and conexion.is_connected():
                cursor.close()
                conexion.close()
    
    cursor.close()
    conexion.close()
    return render_template('finalizar_tarea.html', tarea=instalacion)

# --- Rutas de Instalador ---
@app.route('/mis_tareas_completadas')
@login_required
@instalador_required
def mis_tareas_completadas():
    id_usuario = session['id_usuario']
    conexion = get_db_connection()
    cursor = conexion.cursor(dictionary=True)
    # Consulta solo las tareas completadas asignadas al usuario
    cursor.execute("""
        SELECT t.*, i.nombre AS nombre_instalacion
        FROM tareas t
        JOIN instalaciones i ON t.id_instalacion = i.id_instalacion
        WHERE t.id_usuario_asignado = %s AND t.estado = 'Completada'
        ORDER BY t.fecha_asignacion DESC
    """, (id_usuario,))
    todas_mis_tareas = cursor.fetchall()
    cursor.close()
    conexion.close()
    return render_template('mis_tareas_completadas.html', todas_mis_tareas=todas_mis_tareas)

# --- Rutas API para la nueva funcionalidad ---
def get_mikrotik_users():
    """
    Se conecta al MikroTik y obtiene la lista de usuarios PPPoE secrets.
    """
    users = []
    
    # REEMPLAZA ESTOS VALORES CON LOS DE TU ROUTER MIKROTIK
    router_ip = '10.16.10.1'
    router_port = 8728 # Puerto de la API
    router_user = 'api' # Se corrige la mayúscula a minúscula
    router_password = '1'
    
    api = None
    api_pool = None
    try:
        # Pasa el puerto de la API como un argumento separado
        api_pool = RouterOsApiPool(router_ip, router_user, router_password, port=router_port)
        api = api_pool.get_api()
            
        # Obtener los pppoe secrets del router
        pppoe_secrets = api.talk('/ppp/secret/print')
            
        for secret in pppoe_secrets:
            users.append({
                'username': secret.get('name', ''),
                'service': secret.get('service', ''),
                'phone': secret.get('comment', 'No especificado')
            })
        
        return users
        
    except Exception as e:
        print(f"Error al conectar con MikroTik: {e}")
        # Devuelve una lista vacía en caso de error para evitar fallos
        return []
    finally:
        if api and api_pool:
            api_pool.return_api(api)


@app.route('/api/mikrotik_users', methods=['GET'])
@admin_required
def api_mikrotik_users():
    query = request.args.get('q', '')
    usuarios_mikrotik = get_mikrotik_users()
    
    if query:
        filtered_users = [user for user in usuarios_mikrotik if query.lower() in user['username'].lower()]
        return jsonify(filtered_users)
        
    return jsonify(usuarios_mikrotik)


# --- NUEVA FUNCIÓN: Reparación/Migración ---
@app.route('/reparacion_migracion', methods=['GET', 'POST'])
@admin_required
def reparacion_migracion():
    conexion = get_db_connection()
    cursor = conexion.cursor(dictionary=True)
    
    if request.method == 'POST':
        nombre_cliente = request.form.get('nombre_cliente')
        tipo_servicio = request.form.get('tipo_servicio')
        telefono_cliente = request.form.get('telefono_cliente')
        tipo_tarea = request.form.get('tipo_tarea')
        id_usuario_asignado = request.form.get('id_usuario_asignado')
        descripcion = request.form.get('descripcion')
        
        # En este punto, se simularía la recuperación de datos del MikroTik
        # Como no es posible, se usan los datos del formulario
        
        try:
            # Insertar los datos en la tabla 'instalaciones' como una solicitud pendiente
            sql_insert_instalacion = """
                INSERT INTO instalaciones (nombre, descripcion, estado, tipo_servicio, nombre_cliente, telefono_cliente)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            valores_instalacion = (f"{tipo_tarea} - {nombre_cliente}", descripcion, 'Pendiente', tipo_servicio, nombre_cliente, telefono_cliente)
            cursor.execute(sql_insert_instalacion, valores_instalacion)
            id_instalacion_creada = cursor.lastrowid
            
            # Crear la tarea en la tabla 'tareas' para el técnico asignado
            sql_insert_tarea = """
                INSERT INTO tareas (id_instalacion, id_admin, id_usuario_asignado, tipo_tarea, descripcion, fecha_asignacion, estado)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            valores_tarea = (id_instalacion_creada, session.get('id_usuario'), id_usuario_asignado, tipo_tarea, descripcion, date.today(), 'Pendiente')
            cursor.execute(sql_insert_tarea, valores_tarea)
            
            conexion.commit()
            flash(f"Tarea de {tipo_tarea} asignada con éxito a un técnico.", "success")
            return redirect(url_for('admin'))
        except mysql.connector.Error as err:
            flash(f"Error al asignar la tarea: {err}", "error")
        finally:
            if 'conexion' in locals() and conexion.is_connected():
                cursor.close()
                conexion.close()
                
    cursor.execute("SELECT id_usuario, nombre FROM usuarios WHERE es_admin = 0")
    usuarios_no_admin = cursor.fetchall()
    
    cursor.close()
    conexion.close()
    return render_template('reparacion_migracion.html', usuarios_no_admin=usuarios_no_admin)

# --- Rutas para detalles y reservas ---
@app.route('/instalacion/<int:id>')
@login_required
def detalle_instalacion(id):
    conexion = get_db_connection()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM instalaciones WHERE id_instalacion = %s", (id,))
    instalacion = cursor.fetchone()
    if not instalacion:
        cursor.close()
        conexion.close()
        flash("Instalación no encontrada.", "error")
        return redirect(url_for('index'))
    sql_reservas = "SELECT reservas.*, u.nombre AS nombre_cliente FROM reservas r JOIN usuarios u ON r.id_usuario = u.id_usuario WHERE id_instalacion = %s ORDER BY fecha, hora_inicio"
    cursor.execute(sql_reservas, (id,))
    reservas = cursor.fetchall()
    cursor.close()
    conexion.close()
    return render_template('detalle_instalacion.html', instalacion=instalacion, reservas=reservas)

@app.route('/reservar', methods=['POST'])
@login_required
def reservar():
    id_instalacion = request.form['id_instalacion']
    id_usuario = session['id_usuario']
    fecha = request.form['fecha']
    hora_inicio = request.form['hora_inicio']
    hora_fin = request.form['hora_fin']
    try:
        conexion = get_db_connection()
        cursor = conexion.cursor(dictionary=True) 
        sql_verificacion = """
            SELECT COUNT(*) AS total FROM reservas
            WHERE id_instalacion = %s
            AND fecha = %s
            AND (
                (hora_inicio < %s AND hora_fin > %s) OR
                (hora_inicio >= %s AND hora_inicio < %s) OR
                (hora_fin > %s AND hora_fin <= %s)
            )
        """
        valores_verificacion = (id_instalacion, fecha, hora_fin, hora_inicio, hora_inicio, hora_fin, hora_inicio, hora_fin)
        cursor.execute(sql_verificacion, valores_verificacion)
        resultado_conflicto = cursor.fetchone()
        if resultado_conflicto['total'] > 0:
            flash("La instalación ya está reservada en el horario seleccionado.", "error")
            return redirect(url_for('detalle_instalacion', id=id_instalacion))
        sql_insert = "INSERT INTO reservas (id_instalacion, id_usuario, fecha, hora_inicio, hora_fin) VALUES (%s, %s, %s, %s, %s)"
        valores_insert = (id_instalacion, id_usuario, fecha, hora_inicio, hora_fin)
        cursor.execute(sql_insert, valores_insert)
        conexion.commit()
        nueva_reserva_id = cursor.lastrowid
        cursor.execute("SELECT * FROM reservas WHERE id_reserva = %s", (nueva_reserva_id,))
        reserva = cursor.fetchone()
        cursor.execute("SELECT * FROM instalaciones WHERE id_instalacion = %s", (id_instalacion,))
        instalacion = cursor.fetchone()
        flash("¡Reserva exitosa!", "success")
        return render_template('reserva_exitosa.html', instalacion=instalacion, reserva=reserva)
    except mysql.connector.Error as err:
        flash(f"Error al realizar la reserva: {err}", "error")
        return redirect(url_for('detalle_instalacion', id=id_instalacion))
    finally:
        if 'conexion' in locals() and conexion.is_connected():
            cursor.close()
            conexion.close()

@app.route('/eliminar_reserva/<int:id_reserva>', methods=['POST'])
@login_required
def eliminar_reserva(id_reserva):
    id_usuario = session['id_usuario']
    try:
        conexion = get_db_connection()
        cursor = conexion.cursor()
        sql_verificacion = "SELECT COUNT(*) FROM reservas WHERE id_reserva = %s AND id_usuario = %s"
        cursor.execute(sql_verificacion, (id_reserva, id_usuario))
        pertenece_al_usuario = cursor.fetchone()[0]
        if pertenece_al_usuario:
            sql_eliminar = "DELETE FROM reservas WHERE id_reserva = %s"
            cursor.execute(sql_eliminar, (id_reserva,))
            conexion.commit()
            flash("Reserva eliminada con éxito.", "success")
            return redirect(url_for('mis_reservas'))
        else:
            flash("Error: No tienes permiso para eliminar esta reserva.", "error")
            return redirect(url_for('mis_reservas'))
    except mysql.connector.Error as err:
        flash(f"Error al eliminar la reserva: {err}", "error")
        return redirect(url_for('mis_reservas'))
    finally:
        if 'conexion' in locals() and conexion.is_connected():
            cursor.close()
            conexion.close()

@app.route('/mis_reservas')
@login_required
def mis_reservas():
    id_usuario = session['id_usuario']
    conexion = get_db_connection()
    cursor = conexion.cursor(dictionary=True)
    sql = """
        SELECT r.id_reserva, r.fecha, r.hora_inicio, r.hora_fin, i.nombre as nombre_instalacion 
        FROM reservas r
        JOIN instalaciones i ON r.id_instalacion = i.id_instalacion
        WHERE r.id_usuario = %s
        ORDER BY r.fecha, r.hora_inicio
    """
    cursor.execute(sql, (id_usuario,))
    reservas_usuario = cursor.fetchall()
    cursor.close()
    conexion.close()
    return render_template('mis_reservas.html', reservas=reservas_usuario)

# --- NUEVA FUNCIÓN: Asignar Técnico en Línea ---
@app.route('/asignar_tecnico_en_linea', methods=['POST'])
@admin_required
def asignar_tecnico_en_linea():
    id_instalacion = request.form.get('id_instalacion')
    id_usuario_asignado = request.form.get('id_usuario_asignado')
    
    conexion = get_db_connection()
    cursor = conexion.cursor(dictionary=True)

    try:
        if not id_instalacion or not id_usuario_asignado:
            flash("Faltan datos para asignar el técnico.", "error")
            return redirect(url_for('admin'))

        # Obtener el nombre del técnico
        cursor.execute("SELECT nombre FROM usuarios WHERE id_usuario = %s", (id_usuario_asignado,))
        nombre_tecnico = cursor.fetchone()['nombre']

        # Actualizar la instalación
        sql_update_instalacion = "UPDATE instalaciones SET tecnico_asignado = %s, estado = 'Asignado', id_instalador = %s WHERE id_instalacion = %s"
        valores_update = (nombre_tecnico, id_usuario_asignado, id_instalacion)
        cursor.execute(sql_update_instalacion, valores_update)

        # Crear la tarea en la tabla 'tareas'
        cursor.execute("SELECT nombre, descripcion FROM instalaciones WHERE id_instalacion = %s", (id_instalacion,))
        instalacion = cursor.fetchone()
        
        tipo_tarea = instalacion['nombre'] # Usar el nombre de la instalacion como tipo de tarea
        descripcion_tarea = instalacion['descripcion']

        sql_insert_tarea = "INSERT INTO tareas (id_instalacion, id_admin, id_usuario_asignado, tipo_tarea, descripcion, fecha_asignacion, estado) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        valores_tarea = (id_instalacion, session.get('id_usuario'), id_usuario_asignado, tipo_tarea, descripcion_tarea, date.today(), 'Pendiente')
        cursor.execute(sql_insert_tarea, valores_tarea)
        
        conexion.commit()
        flash("Técnico asignado con éxito y tarea creada.", "success")
    
    except mysql.connector.Error as err:
        flash(f"Error al asignar el técnico: {err}", "error")
        print(f"Error en asignar_tecnico_en_linea: {err}")
    finally:
        if 'conexion' in locals() and conexion.is_connected():
            cursor.close()
            conexion.close()
    
    return redirect(url_for('admin'))


# --- Inicio de la aplicación ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)