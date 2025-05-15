from flask import Flask, render_template, request, redirect, url_for, jsonify,send_file, render_template_string
import bcrypt
from datetime import timedelta
import os
from cryptography.fernet import Fernet
import psycopg2
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from flask import session  # Asegúrate de importar session
import psycopg2.extras
from datetime import datetime, timedelta
import pytz
from mailjet_rest import Client
import random
from weasyprint import HTML
from io import BytesIO

# Cargar variables de entorno
load_dotenv(dotenv_path='variables.env')

app = Flask(__name__, template_folder='templates')

# Configuración de la clave secreta (cargar desde variables de entorno)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    raise ValueError("La clave secreta no está definida. Establezca FLASK_SECRET_KEY en las variables de entorno.")

app.permanent_session_lifetime = timedelta(minutes=30)

# Cargar o generar la clave para cifrado
key_path = "secret.key"
if os.path.exists(key_path):
    with open(key_path, "rb") as key_file:
        key = key_file.read()
else:
    key = Fernet.generate_key()
    with open(key_path, "wb") as key_file:
        key_file.write(key)
cipher_suite = Fernet(key)

# Configuración de PostgreSQL (para registro y login)
app.config['POSTGRES_HOST'] = os.getenv('POSTGRES_HOST')
app.config['POSTGRES_USER'] = os.getenv('POSTGRES_USER')
app.config['POSTGRES_PASSWORD'] = os.getenv('POSTGRES_PASSWORD')
app.config['POSTGRES_DB'] = os.getenv('POSTGRES_DB')

# Inicializando PostgreSQL y Bcrypt
bcrypt = Bcrypt(app)

# Conexión a PostgreSQL
def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
        dbname=os.getenv('POSTGRES_DB')
    )
    return conn

#Info de ApiMail
mailjet_api_key = os.getenv('MAILJET_API_KEY')
mailjet_api_secret = os.getenv('MAILJET_API_SECRET')
mailjet_correos = Client(auth=(mailjet_api_key, mailjet_api_secret), version='v3.1')
mailjet_contacto = Client(auth=(mailjet_api_key, mailjet_api_secret), version='v3')
# IDs de las listas en Mailjet (debes obtener estos IDs desde el panel de Mailjet)
LISTA_USUARIOS_ID = "10530275"  # Reemplaza con el ID de la lista de usuarios
LISTA_TUTORES_ID = "10530274"    # Reemplaza con el ID de la lista de tutores

def agregar_contacto_a_lista(email, nombre, lista_id):
    """
    Agrega un contacto a una lista específica en Mailjet.
    """
    # Paso 1: Crear o obtener el contacto
    data_contacto = {
        "IsExcludedFromCampaigns": "True",
        "Name": nombre,
        "Email": email
    }
    resultado_contacto = mailjet_contacto.contact.create(data=data_contacto)

    if resultado_contacto.status_code != 201:
        print(f"Error al crear el contacto: {resultado_contacto.status_code}")
        return False

    contacto_id = resultado_contacto.json()['Data'][0]['ID']

    # Paso 2: Agregar el contacto a la lista
    data_lista = {
        "ContactID": contacto_id,
        "ListID": lista_id,
        "IsUnsubscribed": "false"
    }
    resultado_lista = mailjet_contacto.contactslist_managecontact.create(data=data_lista)

    if resultado_lista.status_code != 201:
        print(f"Error al agregar el contacto a la lista: {resultado_lista.status_code}")
        return False

    return True

def enviar_correo_bienvenida(destinatario, registro, correo):
    template_id = 6834687  # ID de template en Mailjet

    data = {
        'Messages': [
            {
                "From": {
                    "Email": "migueromoudg@gmail.com",
                    "Name": "Escuela Bosco"
                },
                "To": [
                    {
                        "Email": destinatario,
                        "Name": destinatario
                    }
                ],
                "TemplateID": template_id,
                "TemplateLanguage": True,
                "Subject": "Bienvenido/a al Colegio Parroquial Don Bosco",
                "Variables": {
                    "registro": str(registro),  # Asegúrate de que sea una cadena
                    "correo": str(correo)       # Asegúrate de que sea una cadena
                }
            }
        ]
    }

    try:
        print("Datos que se enviarán a Mailjet:", data)  # Depuración: Imprimir los datos
        result = mailjet_correos.send.create(data=data)
        print("Respuesta de Mailjet:", result.status_code, result.json())  # Depuración: Imprimir la respuesta

        if result.status_code == 200:
            return True
        else:
            print(f"Error al enviar el correo: {result.status_code}")
            print(f"Detalles del error: {result.json()}")  # Depuración: Imprimir detalles del error
            return False
    except Exception as e:
        print(f"Error al enviar el correo: {e}")
        return False

def generar_contraseña():
    numeros = ''.join([str(random.randint(0, 9)) for _ in range(5)])
    return f"BOSCO@{numeros}"


def enviar_correo(destinatario, contraseña):
    # ID del template de Mailjet (obtén este ID desde el panel de Mailjet)
    template_id = 6834746  # Reemplaza con el ID de tu template en Mailjet

    data = {
        'Messages': [
            {
                "From": {
                    "Email": "migueromoudg@gmail.com",  # Cambia esto por tu correo
                    "Name": "Escuela Bosco"
                },
                "To": [
                    {
                        "Email": destinatario,
                        "Name": destinatario
                    }
                ],
                "TemplateID": template_id,  # Usar el template de Mailjet
                "TemplateLanguage": True,   # Habilitar el uso de variables
                "Subject": "Recuperación de Contraseña",
                "Variables": {  # Pasar las variables al template
                    "contraseña": contraseña  # La variable que definiste en el template
                }
            }
        ]
    }

    try:
        result = mailjet_correos.send.create(data=data)
        if result.status_code == 200:
            return True
        else:
            print(f"Error al enviar el correo: {result.status_code}")
            return False
    except Exception as e:
        print(f"Error al enviar el correo: {e}")
        return False

############################################################################################################################################################################################




@app.route('/')
def home():
    return render_template('Index.html')



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        id_usuario = int(request.form.get("registro"))
        password = request.form.get("password")



        # Verificar si el usuario existe en la base de datos PostgreSQL
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE id_usuario = %s", (id_usuario,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()


        if user and bcrypt.check_password_hash(user[-3], password):  # user[-2] es la columna de la contraseña sin encriptar
            session['id_usuario'] = user[0]  # Suponiendo que user[0] es el ID del usuario
            session['rol'] = user[-4]  # Almacenar el rol en la sesión
            # Redirigir según el rol
            if user[-4] == 'admin':
                return redirect(url_for('admin'))
            elif user[-4] == 'profesor':
                return redirect(url_for('profesor'))
            elif user[-4] == 'director':
                return redirect(url_for('director'))
            else:
                return "Rol desconocido", 400  # Agregado para capturar cualquier rol no esperado
        else:
            # Aquí se agrega el mensaje de error
            return render_template('login.html', mensaje_error="Usuario y/o contraseña incorrectos")
        
    return render_template('login.html')


@app.route('/recuperar_contraseña', methods=['GET', 'POST'])
def recuperar_contraseña():
    if request.method == 'POST':
        registro = request.form['registro']
        email = request.form['email']

        # Conectar a la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM usuarios WHERE id_usuario = %s AND correo = %s", (registro, email))
        usuario = cursor.fetchone()

        if usuario:
            nueva_contraseña = generar_contraseña()
            contraseña_cifrada =  bcrypt.generate_password_hash(nueva_contraseña).decode('utf-8')
            cursor.execute("UPDATE usuarios SET contrasena = %s WHERE id_usuario = %s", (contraseña_cifrada, registro))
            conn.commit()
            enviar_correo(email, nueva_contraseña)
            conn.close()

        return redirect(url_for('login'))

    return render_template('recuperar.html')

@app.route('/profesor', methods=['GET', 'POST'])
def profesor():
    # Verificar si el usuario está autenticado
    if 'id_usuario' not in session or session['rol'] != 'profesor':
        return redirect(url_for('login'))  # Redirigir al login si no está autenticado

    # Obtener el ID del profesor desde la sesión
    id_profesor = session['id_usuario']

    # Conectar a la base de datos
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Obtener las materias del profesor
        cursor.execute(
            "SELECT id_materia, nombre FROM materia WHERE id_usuario = %s",
            (id_profesor,)
        )
        materias = cursor.fetchall()  # Obtener todas las materias
    except Exception as e:
        print(f"Error al obtener las materias: {str(e)}")
        materias = []  # En caso de error, devolver una lista vacía
    finally:
        cursor.close()
        conn.close()

    # Pasar las materias a la plantilla
    return render_template('profesor.html', materias=materias, materias2=get_materias(), alumnos=get_alumnos_reportes())

@app.route('/detalle_materia/<int:id_materia>', methods=['GET'])
def detalle_materia(id_materia):
    tz = pytz.timezone('America/Mexico_City')
    fecha_hoy = datetime.now(tz).date()
    fechas = [str(fecha_hoy - timedelta(days=i)) for i in range(5)]  # Últimos 5 días (hoy y 4 días pasados)
    fecha_mas_antigua = fecha_hoy - timedelta(days=5)  # Día a eliminar (hace 5 días)
    """
    # Fechas para misa (últimos 3 domingos)
    fechas_misa = []
    domingos_encontrados = 0
    dia_actual = 0
    
    while domingos_encontrados < 3:
        fecha = fecha_hoy - timedelta(days=dia_actual)
        if fecha.weekday() == 6:  # 6 es domingo
            fechas_misa.append(str(fecha))
            domingos_encontrados += 1
        dia_actual += 1
    """    
    conn = get_db_connection()
    cursor = conn.cursor()

    # Eliminar asistencias más antiguas (todas las anteriores a hace 5 días)
    eliminar_asistencias_query = "DELETE FROM asistencia WHERE fecha < %s AND id_materia = %s"
    cursor.execute(eliminar_asistencias_query, (fecha_mas_antigua, id_materia))
    conn.commit()

    # Obtener los estudiantes asociados con la materia
    estudiantes_query = """
        SELECT DISTINCT e.id_alumno, e.nombre, e.apellido_paterno
        FROM alumno e
        JOIN parciales m ON e.id_alumno = m.id_alumno
        WHERE m.id_materia = %s
    """
    cursor.execute(estudiantes_query, (id_materia,))
    estudiantes = cursor.fetchall()

    # Verificar si hay registros de asistencia para los últimos 5 días y crearlos si no existen
    for fecha in fechas:
        asistencia_dia_query = "SELECT COUNT(*) FROM asistencia WHERE fecha = %s AND id_materia = %s"
        cursor.execute(asistencia_dia_query, (fecha, id_materia))
        asistencia_dia = cursor.fetchone()[0]

        # Si no hay registros de asistencia para la fecha específica, crearlos
        if asistencia_dia == 0:
            for estudiante in estudiantes:
                insertar_asistencia_query = """
                    INSERT INTO asistencia (id_estudiante, id_materia, fecha, estado) 
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(insertar_asistencia_query, (estudiante[0], id_materia, fecha, True))  # Estado inicial: Asistió
            conn.commit()


    # Obtener las asistencias de los últimos 5 días
    asistencias_query = """
        SELECT a.id_estudiante, a.fecha, a.estado
        FROM asistencia a
        WHERE a.id_materia = %s AND a.fecha IN (%s, %s, %s, %s, %s)
    """
    cursor.execute(asistencias_query, (id_materia, fechas[0], fechas[1], fechas[2], fechas[3], fechas[4]))
    asistencias = cursor.fetchall()

    # Organizar las asistencias por estudiante y fecha
    asistencia_por_estudiante = {estudiante[0]: {fecha: 0 for fecha in fechas} for estudiante in estudiantes}
    for id_estudiante, fecha, estado in asistencias:
        asistencia_por_estudiante[id_estudiante][str(fecha)] = estado

    # Get the absences for the students (faltas)
    cursor.execute("""
        SELECT id_alumno, faltas
        FROM parciales
        WHERE parcial = 1
    """)
    faltas_por_estudiante = {row[0]: row[1] for row in cursor.fetchall()}

    cursor.close()
    conn.close()

    return render_template('detalle_materia.html', 
                           materia_id=id_materia, 
                           estudiantes=estudiantes, 
                           fechas=fechas, 
                           asistencia_por_estudiante=asistencia_por_estudiante, faltas_por_estudiante=faltas_por_estudiante)

@app.route('/actualizar_asistencia', methods=['POST'])
def actualizar_asistencia():
    try:
        data = request.get_json()
        estudiante_id = data.get('estudiante_id')
        fecha = data.get('fecha')
        estado = data.get('estado')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Obtener el estado actual en la base de datos
        cursor.execute(
            "SELECT estado FROM asistencia WHERE id_estudiante = %s AND fecha = %s",
            (estudiante_id, fecha)
        )
        resultado = cursor.fetchone()

        if resultado is None:
            return jsonify({"success": False, "error": "Registro no encontrado"}), 404
        
        estado_actual = resultado[0]

        # Si el estado no ha cambiado, no hacer nada
        if estado_actual == estado:
            return jsonify({"success": False, "error": "Estado ya actualizado"}), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    # Actualizar el estado de la asistencia
    actualizar_asistencia_query = """
        UPDATE asistencia 
        SET estado = %s 
        WHERE id_estudiante = %s AND fecha = %s
    """
    cursor.execute(actualizar_asistencia_query, (estado, estudiante_id, fecha))
    conn.commit()

    # Modificar la columna faltas en la tabla parciales según el estado
    if estado == False:  # Si el estado es false, incrementa la columna faltas
        actualizar_faltas_query = """
            UPDATE parciales
            SET faltas = faltas + 1
            WHERE id_alumno = %s AND parcial=1
        """
    elif estado == True:  # Si el estado es true, decrementa la columna faltas
        actualizar_faltas_query = """
            UPDATE parciales
            SET faltas = faltas - 1
            WHERE id_alumno = %s AND parcial=1
        """
    cursor.execute(actualizar_faltas_query, (estudiante_id,))
    conn.commit()


    cursor.close()
    conn.close()
    return jsonify({"success": True})  # Respuesta JSON al frontend


def obtener_calificaciones(parcial, id_profesor):
    """Función para obtener calificaciones de un parcial específico para un profesor"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT a.id_alumno, a.nombre, a.apellido_paterno, 
               p.parcial, p.participacion, 
               p.ejercicios_practicas, p.tareas_trabajo, 
               p.examen, p.calificacion_parcial
        FROM parciales p
        JOIN alumno a ON p.id_alumno = a.id_alumno
        JOIN materia m ON p.id_materia = m.id_materia
        WHERE p.parcial = %s AND m.id_usuario = %s
    """
    
    cursor.execute(query, (parcial, id_profesor))
    calificaciones = cursor.fetchall()
    conn.close()

    return calificaciones


@app.route('/obtener_calificaciones', methods=['POST'])
def obtener_calificaciones_route():
    """Route para devolver calificaciones en formato JSON solo para el profesor"""
    data = request.get_json()
    parcial = data.get('parcial', 1)  # Por defecto, parcial 1
    id_profesor = session.get('id_usuario')  # Se obtiene el ID del profesor de la sesión
    
    if not id_profesor:
        return jsonify({"success": False, "error": "Acceso no autorizado"}), 403
    
    calificaciones = obtener_calificaciones(parcial, id_profesor)
    
    resultado = [
        {
            "id": fila[0],
            "nombre": fila[1],
            "apellido": fila[2],
            "parcial": fila[3],
            "participacion": fila[4],
            "ejercicios_practicas": fila[5],
            "tareas_trabajo": fila[6],
            "examen": fila[7],
            "calificacion_parcial": fila[8]
        }
        for fila in calificaciones
    ]

    return jsonify({"success": True, "calificaciones": resultado})

@app.route('/actualizar_calificacion', methods=['POST'])
def actualizar_calificacion():
    """Actualiza una calificación en la base de datos"""
    data = request.get_json()
    id_alumno = data.get('id_alumno')
    parcial_id = data.get('parcial_id')  # Identificador del parcial
    materia_id = data.get('materia_id')  # Identificador de la materia
    campo = data.get('campo')  # Puede ser "participacion", "ejercicios_practicas", etc.
    nueva_calificacion = data.get('nueva_calificacion')
    print("Datos recibidos:", data)  # <-- Agregamos esto para depurar
    print(materia_id)
    if not id_alumno or not parcial_id or not materia_id or not campo or nueva_calificacion is None:
        print("Datos inválidos:", data)
        return jsonify({"success": False, "error": "Datos inválidos"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Actualización de la calificación correspondiente
        query = f"""
            UPDATE parciales
            SET {campo} = %s
            WHERE id_alumno = %s AND parcial = %s AND id_materia = %s
        """
        cursor.execute(query, (nueva_calificacion, id_alumno, parcial_id, materia_id))
        print("Filas afectadas :", cursor.rowcount)  # <-- Agregamos esto para ver si se modificó algo
        conn.commit()
        conn.close()

        return jsonify({"success": True})
    except Exception as e:
        print("Error al actualizar la calificación:", e)
        return jsonify({"success": False, "error": "Error en la base de datos"}), 500



@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/contratar', methods=['GET', 'POST'])
def contratar():
    if request.method == 'POST':
        # Obtener los datos del formulario
        nombre = request.form['nombre']
        apellido_paterno = request.form['apellido_paterno']
        apellido_materno = request.form['apellido_materno']
        fecha_nacimiento = request.form['fecha_nacimiento']
        rol = request.form['rol']
        correo_colaborador = request.form.get('correo_colaborador')  # Campo de correo

        # Extraer el año de nacimiento
        año_nacimiento = fecha_nacimiento.split('-')[0]  # Formato: YYYY-MM-DD

        # Generar la contraseña por defecto
        contraseña_por_defecto = f"BOSCO@{año_nacimiento}"
        print(contraseña_por_defecto)

        # Cifrar la contraseña
        contraseña_cifrada = bcrypt.generate_password_hash(contraseña_por_defecto).decode('utf-8')

        # Conectar a la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insertar los datos en la tabla usuarios
        try:
            cursor.execute(
                "INSERT INTO usuarios (nombre, apellido_paterno, apellido_materno, rol, contrasena,fecha_nacimiento,correo) "
                "VALUES (%s, %s, %s, %s, %s, %s,%s) RETURNING id_usuario",
                (nombre, apellido_paterno, apellido_materno, rol, contraseña_cifrada, fecha_nacimiento,correo_colaborador)
            )
            id_usuario = str(cursor.fetchone()[0])
            print(correo_colaborador)
            print(id_usuario)
            conn.commit()  # Guardar los cambios en la base de datos
            agregar_contacto_a_lista(correo_colaborador, nombre, LISTA_USUARIOS_ID)
            print(" - ")
            enviar_correo_bienvenida(correo_colaborador, id_usuario, correo_colaborador)

        except Exception as e:
            conn.rollback()  # Revertir cambios en caso de error
            print(f"Error al registrar el usuario: {str(e)}")  # Opcional: Imprimir el error en la consola
        finally:
            cursor.close()
            conn.close()
        # Redirigir a la página de administración
        return redirect(url_for('admin'))
    
    if request.method == 'GET':
        return render_template('contratacion.html')  # Muestra el formulario

@app.route('/inscripcion', methods=['GET', 'POST'])
def inscripcion():
    if request.method == 'POST':
        # Obtener los datos del formulario
        nombre = request.form['nombre']
        apellido_paterno = request.form['apellido_paterno']
        apellido_materno = request.form['apellido_materno']
        campus = request.form['escuela_inscripcion']
        nivel = request.form['nivel']
        grado = request.form['grado']
        curp = request.form['curp']
        fecha_nacimiento = request.form['fecha_nacimiento']
        alergias = request.form['alergias']
        capilla = request.form['capilla']
        beca = request.form['beca']
        sexo = request.form['Sexo']
        tipo_sangre = request.form['tipo_sangre']

        tiene_familia = request.form.get('tiene_familia')  # Checkbox: "Tiene familia registrada"
        correo_familiar = request.form.get('correo_familiar')  # Campo de correo


        if tiene_familia:
            # Si el usuario tiene una familia registrada, tomamos el ID de la familia
            id_familia = request.form.get('id_familia')
            if not id_familia or not id_familia.isdigit():
                return "Por favor ingrese un ID de Familia válido", 400
            id_familia = int(id_familia)

        else:
            # Si no tiene familia registrada, tomamos los datos de nueva familia
            tutor = request.form.get('tutor')
            tel_emergencia = request.form.get('tel_emergencia')
            
            if not tutor or not tel_emergencia or not correo_familiar:
                return "Por favor ingrese todos los campos para la nueva familia", 400
            
        
        # Conectar a la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
             # Insertar la familia si no existe
            if not tiene_familia:
                cursor.execute(
                    "INSERT INTO familia (tutor, tel_emergencia, correo) VALUES (%s, %s, %s) RETURNING id_familia",
                    (tutor, tel_emergencia, correo_familiar)
                )
                id_familia = cursor.fetchone()[0]
                agregar_contacto_a_lista(correo_familiar, tutor,LISTA_TUTORES_ID)
            # Insertar los datos del alumno
            cursor.execute(
                "INSERT INTO alumno (nombre, apellido_paterno, apellido_materno, nivel, grado, campus, id_familia) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id_alumno",
                (nombre, apellido_paterno, apellido_materno, nivel, grado, campus, id_familia)
            )
            id_alumno = cursor.fetchone()[0]

            # Insertar los datos generales
            cursor.execute(
                "INSERT INTO datos_generales (id_alumno, curp, sexo, tipo_sangre, alergias, capilla, beca, fecha_nacimiento) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (id_alumno, curp, sexo, tipo_sangre, alergias, capilla, beca, fecha_nacimiento)
            )
            conn.commit()  # Guardar los cambios en la base de datos
        except Exception as e:
            conn.rollback()  # Revertir cambios en caso de error
            print(f"Error al registrar el alumno: {str(e)}")  # Opcional: Imprimir el error en la consola
            return "Error al registrar el alumno", 500
        finally:
            cursor.close()
            conn.close()

        # Redirigir a la página de administración o confirmación
        return redirect(url_for('admin'))
    
    if request.method == 'GET':
        return render_template('Inscripcion.html')  # Muestra el formulario

@app.route('/director', methods=['GET', 'POST'])
def director():
    if 'id_usuario' not in session or session['rol'] != 'director':
        return redirect(url_for('login'))
    return render_template('director.html', materias=get_materias(), alumnos=get_alumnos_reportes())  # Asegúrate de tener este template

def get_materias():
    conn = get_db_connection()
    id_usuario = session['id_usuario']  # Obtenlo desde la sesión de Flask
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)  # Usa DictCursor aquí
    cursor.execute("SELECT id_materia, nombre FROM materia WHERE id_usuario = %s", (id_usuario,))
    materias = cursor.fetchall()
    if not materias:
        cursor.execute("SELECT id_materia, nombre FROM materia WHERE id_usuario = 1")
        materias = cursor.fetchall()
    cursor.close()
    conn.close()
    print(materias)
    return materias

def get_alumnos_reportes():
    rol = session['rol']
    id_usuario = session['id_usuario'] 
    if rol == "director":
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)  # Usa DictCursor aquí
        cursor.execute("SELECT id_alumno, nombre, apellido_paterno, apellido_materno FROM alumno")
        alumnos = cursor.fetchall()
        cursor.close()
        conn.close()
        print (alumnos)
        print("---------------------------------------------")
        return alumnos
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)  # Usa DictCursor aquí
    estudiantes_query = """
    SELECT DISTINCT e.id_alumno, e.nombre, e.apellido_paterno
    FROM alumno e
    JOIN parciales m ON e.id_alumno = m.id_alumno
    JOIN materia mat ON m.id_materia = mat.id_materia
    WHERE mat.id_usuario = %s
    """
    cursor.execute(estudiantes_query, (id_usuario,))
    alumnos = cursor.fetchall()
    cursor.close()
    conn.close()
    print (alumnos)
    print("---------------------------------------------")
    return alumnos

@app.route('/generar_reporte', methods=['GET', 'POST'])
def generar_reporte():
    conn = get_db_connection()
    if request.method == 'POST':
        id_materia = request.form.get('id_materia')
        id_alumno = request.form.get('nombre_alumno')
        fecha = request.form.get('fecha')
        comentarios = request.form.get('comentarios')
        id_usuario = session['id_usuario']
        try:
            with conn.cursor() as cursor:
                sql = """
                    INSERT INTO reportes (id_alumno, id_usuario, id_materia, fecha, reporte)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (id_alumno, id_usuario, id_materia, fecha, comentarios))
                conn.commit()
                print("Reporte registrado")
                # Retornar el PDF directamente
                return pdf_reporte(id_alumno,fecha,comentarios,id_materia,id_usuario)
        except Exception as e:
            print("Error al guardar el reporte:", e)
        finally:
            conn.close()

    return redirect(url_for('generar_reporte'))

def pdf_reporte(id_alumno,fecha,comentarios,id_materia,id_usuario):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Obtener nombre de la materia
    cursor.execute("""
        SELECT nombre
        FROM materia
        WHERE id_materia = %s
    """, (id_materia,))
    nombre_materia = cursor.fetchone()[0]
    print(nombre_materia)
    if not nombre_materia:
        cursor.close()
        conn.close()
        return "Materia no encontrada", 404

    # Obtener nombre completo del profesor
    cursor.execute("""
        SELECT nombre, apellido_paterno, apellido_materno
        FROM usuarios
        WHERE id_usuario = %s
    """, (id_usuario,))
    datos_profesor = cursor.fetchone()
    if not datos_profesor:
        cursor.close()
        conn.close()
        return "Profesor no encontrado", 404


    # Datos del alumno
    cursor.execute("""
        SELECT nombre, apellido_paterno, apellido_materno, nivel, grado, campus
        FROM alumno
        WHERE id_alumno = %s
    """, (id_alumno,))
    datos_alumno = cursor.fetchone()
    if not datos_alumno:
        cursor.close()
        conn.close()
        return "Alumno no encontrado", 404

    alumno = {
        'nombre': datos_alumno[0],
        'apellido_paterno': datos_alumno[1],
        'apellido_materno': datos_alumno[2],
        'nivel': datos_alumno[3],
        'grado': datos_alumno[4],
        'campus': datos_alumno[5],
    }

    plantilla_html = '''
        <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Reporte Disciplinar</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #fff;
                color: #000;
                margin: 40px;
                line-height: 1.6;
            }

            header {
                text-align: center;
                border-bottom: 2px solid rgb(34, 113, 169);
                padding-bottom: 10px;
                margin-bottom: 30px;
            }

            header h1 {
                color: rgb(34, 113, 169);
                font-size: 24px;
                margin: 0;
            }

            .section {
                margin-bottom: 20px;
            }

            .section h2 {
                font-size: 18px;
                color: rgb(34, 113, 169);
                margin-bottom: 10px;
            }

            .info {
                background-color: #f4f4f4;
                padding: 15px;
                border-radius: 8px;
                border: 1px solid #ccc;
            }

            .info p {
                margin: 5px 0;
            }

            .comentarios {
                background-color: #eef7ff;
                padding: 15px;
                border-radius: 8px;
                border: 1px solid #4D869C;
            }

            footer {
                margin-top: 50px;
                font-size: 12px;
                text-align: center;
                color: #888;
            }
        </style>
    </head>
    <body>

    <header>
        <h1>Reporte Disciplinar</h1>
    </header>

    <section class="section">
        <h2>Información general</h2>
        <div class="info">
            <p><strong>Materia:</strong> {{ nombre_materia }}</p>
            <p><strong>Alumno:</strong> {{ alumno.nombre }} {{ alumno.apellido_paterno }} {{ alumno.apellido_materno }}</p>
            <p><strong>Fecha:</strong> {{ fecha }}</p>
        </div>
    </section>

    <section class="section">
        <h2>Comentarios</h2>
        <div class="comentarios">
            <p>{{ comentarios }}</p>
        </div>
    </section>

    <footer>
        Generado automáticamente por el sistema NeoSchool.
    </footer>

    </body>
    </html>
    '''

    html_rendered = render_template_string(plantilla_html, alumno=alumno,fecha=fecha,comentarios=comentarios,nombre_materia=nombre_materia)
    pdf = HTML(string=html_rendered).write_pdf()

    return send_file(BytesIO(pdf), download_name="reporte.pdf", as_attachment=True)


@app.route('/descargar_calificaciones')
def descargar_calificaciones():
    id_alumno = request.args.get('id_alumno')
    parcial_id = request.args.get('parcial_id')
    materia_id = request.args.get('materia_id')

    # Aquí generas el archivo (por ejemplo, PDF o CSV) y lo devuelves con send_file o similar
    return descargar_boleta(id_alumno,materia_id)

def descargar_boleta(id_alumno,materia_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Datos del alumno
    cursor.execute("""
        SELECT nombre, apellido_paterno, apellido_materno, nivel, grado, campus
        FROM alumno
        WHERE id_alumno = %s
    """, (id_alumno,))
    datos_alumno = cursor.fetchone()
    if not datos_alumno:
        cursor.close()
        conn.close()
        return "Alumno no encontrado", 404

    alumno = {
        'nombre': datos_alumno[0],
        'apellido_paterno': datos_alumno[1],
        'apellido_materno': datos_alumno[2],
        'nivel': datos_alumno[3],
        'grado': datos_alumno[4],
        'campus': datos_alumno[5],
    }

    # Calificaciones por parcial
    cursor.execute("""
        SELECT parcial, participacion, ejercicios_practicas, tareas_trabajo,
            examen, asistencia_misa, calificacion_parcial
        FROM parciales
        WHERE id_alumno = %s AND id_materia = %s
        ORDER BY parcial ASC
    """, (id_alumno,materia_id))
    filas = cursor.fetchall()
    cursor.close()
    conn.close()

    califs = []
    for fila in filas:
        califs.append({
            'parcial': fila[0],
            'participacion': fila[1],
            'ejercicios': fila[2],
            'tareas': fila[3],
            'examen': fila[4],
            'asistencia': fila[5],
            'promedio': fila[6]
        })

    plantilla_html = '''
    <html>
    <head>
        <style>
            body { font-family: Arial; margin: 30px; }
            h1, h2, p { text-align: center; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { border: 1px solid #000; padding: 8px; text-align: center; }
            th { background-color: #2271a9; color: white; }
        </style>
    </head>
    <body>
        <h1>NeoSchool - Boleta de Calificaciones</h1>
        <p><strong>Alumno:</strong> {{ alumno.nombre }} {{ alumno.apellido_paterno }} {{ alumno.apellido_materno }}</p>
        <p><strong>Nivel:</strong> {{ alumno.nivel }} | <strong>Grado:</strong> {{ alumno.grado }} | <strong>Campus:</strong> {{ alumno.campus }}</p>

        <table>
            <tr>
                <th>Parcial</th>
                <th>Participación</th>
                <th>Ejercicios</th>
                <th>Tareas</th>
                <th>Examen</th>
                <th>Asistencia</th>
                <th>Promedio</th>
            </tr>
            {% for c in califs %}
            <tr>
                <td>{{ c.parcial }}</td>
                <td>{{ c.participacion }}</td>
                <td>{{ c.ejercicios }}</td>
                <td>{{ c.tareas }}</td>
                <td>{{ c.examen }}</td>
                <td>{{ c.asistencia }}</td>
                <td>{{ c.promedio }}</td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    '''

    html_rendered = render_template_string(plantilla_html, alumno=alumno, califs=califs)
    pdf = HTML(string=html_rendered).write_pdf()

    return send_file(BytesIO(pdf), download_name="boleta.pdf", as_attachment=True)




@app.route('/agregar_materia', methods=['GET', 'POST'])
def agregar_materia():
    if 'id_usuario' not in session or (session['rol'] != 'admin' and session['rol'] != 'director'):
        return redirect(url_for('login'))  # Solo administradores pueden agregar materias

    if request.method == 'POST':
        nombre = request.form['nombre']
        id_usuario = request.form['id_usuario']  # Maestro seleccionado
        alumnos_seleccionados = request.form.getlist('alumnos')  # Lista de alumnos seleccionados
        if not alumnos_seleccionados:
            return render_template('agregar_materia.html', mensaje="Debes seleccionar al menos un alumno.", maestros=get_maestros(), alumnos=get_alumnos())

        #print(f"🔹 Nombre de la materia: {nombre}")
        #print(f"🔹 ID del maestro: {id_usuario}")
        #print(f"🔹 Alumnos seleccionados: {alumnos_seleccionados}")

        # Insertar la materia en la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            print(cursor.query)
            cursor.execute(
                "INSERT INTO materia (nombre, id_usuario) VALUES (%s, %s) RETURNING id_materia",
                (nombre, id_usuario)
            )
            id_materia = cursor.fetchone()[0]  # Obtener el ID de la materia recién insertada
            conn.commit()
            # Insertar los alumnos en la relación materia-alumno
            for id_alumno in alumnos_seleccionados:
                for parcial in range(1, 6):  # 5 parciales (1 al 5)
                    participacion = 10
                    ejercicios_practicas = 10
                    tareas_trabajo = 10
                    examen = 10
                    asistencia_misa = 0
                    retardos = 0

                    # Calcular la calificación final (promedio de los primeros 4 valores)
                    calificacion_parcial = (participacion + ejercicios_practicas + tareas_trabajo + examen) / 4
                    print(cursor.query)
                    cursor.execute(
                        """INSERT INTO parciales 
                        (id_alumno, id_materia, parcial, participacion, ejercicios_practicas, 
                        tareas_trabajo, examen, asistencia_misa, retardos, calificacion_parcial) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (id_alumno, id_materia, parcial, participacion, 
                        ejercicios_practicas, tareas_trabajo, examen,   
                        asistencia_misa, retardos, calificacion_parcial)
                    )

            # 3️⃣ Confirmar los cambios
            conn.commit()
            mensaje = "Materia y alumnos agregados exitosamente."
        except Exception as e:
            conn.rollback()
            mensaje = f"Error al agregar la materia: {str(e)}"
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('admin'))

    # Obtener la lista de maestros y alumnos para el formulario
    return render_template('agregar_materia.html', maestros=get_maestros(), alumnos=get_alumnos())


def get_maestros():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)  # Usa DictCursor aquí
    cursor.execute("SELECT id_usuario, nombre, apellido_paterno FROM usuarios WHERE rol = 'profesor'")
    maestros = cursor.fetchall()
    cursor.close()
    conn.close()
    print(maestros)
    return maestros

import psycopg2.extras

def get_alumnos():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)  # Usa DictCursor aquí
    cursor.execute("SELECT id_alumno, nombre, apellido_paterno, apellido_materno FROM alumno")
    alumnos = cursor.fetchall()
    cursor.close()
    conn.close()
    print (alumnos)
    return alumnos


@app.route('/cambiar_contrasena', methods=['GET', 'POST'])
def cambiar_contrasena():
    if 'id_usuario' not in session:
        return redirect(url_for('login'))  # Redirigir al login si no está autenticado

    mensaje = None

    if request.method == 'POST':
        id_usuario = session['id_usuario']
        contraseña_actual = request.form['current_password']
        nueva_contraseña = request.form['new_password']
        confirmar_contraseña = request.form['confirm_password']

        # Verificar que las nuevas contraseñas coincidan
        if nueva_contraseña != confirmar_contraseña:
            mensaje = "Las nuevas contraseñas no coinciden."
        else:
            # Obtener la contraseña actual del usuario desde la base de datos
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT contrasena FROM usuarios WHERE id_usuario = %s", (id_usuario,))
            usuario = cursor.fetchone()
            cursor.close()
            conn.close()

            if usuario and bcrypt.check_password_hash(usuario[0], contraseña_actual):
                # Encriptar la nueva contraseña
                nueva_contraseña_encriptada = bcrypt.generate_password_hash(nueva_contraseña).decode('utf-8')

                # Actualizar la contraseña en la base de datos
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE usuarios SET contrasena = %s WHERE id_usuario = %s",
                    (nueva_contraseña_encriptada, id_usuario)
                )
                conn.commit()
                cursor.close()
                conn.close()

                mensaje = "Contraseña cambiada exitosamente."
                
                # Redireccionar según el rol del usuario
                rol = session.get('rol', None)
                if rol == 'admin':
                    return render_template('admin.html', mensaje="Contraseña actualizada correctamente")
                elif rol == 'profesor':
                    return render_template('profesor.html', mensaje="Contraseña actualizada correctamente")
                else:
                    return redirect(url_for('director'))  # Página principal por defecto

            else:
                mensaje = "La contraseña actual es incorrecta."

    return render_template('cambiar_contrasena.html', mensaje=mensaje)

@app.route('/logout')
def logout():
    session.clear()  # Elimina todos los datos de sesión
    return redirect(url_for('login'))  # Redirige a la página de login

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
