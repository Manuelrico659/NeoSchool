from flask import Flask, render_template, request, redirect, url_for
import bcrypt
from datetime import timedelta
import os
from cryptography.fernet import Fernet
import psycopg2
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv

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

@app.route('/')
def home():
    return render_template('Index.html')

bcrypt = Bcrypt(app)

@app.route('/contratar', methods=['POST'])
def contratar():
    if request.method == 'POST':
        # Obtener los datos del formulario
        nombre = request.form['nombre']
        apellido_paterno = request.form['apellido_paterno']
        apellido_materno = request.form['apellido_materno']
        fecha_nacimiento = request.form['fecha_nacimiento']
        rol = request.form['rol']

        # Extraer el año de nacimiento
        año_nacimiento = fecha_nacimiento.split('-')[0]  # Formato: YYYY-MM-DD

        # Generar la contraseña por defecto
        contraseña_por_defecto = f"BOSCO@{año_nacimiento}"

        # Cifrar la contraseña
        contraseña_cifrada = bcrypt.generate_password_hash(contraseña_por_defecto).decode('utf-8')

        # Conectar a la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insertar los datos en la tabla usuarios
        try:
            cursor.execute(
                "INSERT INTO usuarios (nombre, apellido_paterno, apellido_materno, fecha_nacimiento, rol, password) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (nombre, apellido_paterno, apellido_materno, fecha_nacimiento, rol, contraseña_cifrada)
            )
            conn.commit()  # Guardar los cambios en la base de datos
        except Exception as e:
            conn.rollback()  # Revertir cambios en caso de error
            print(f"Error al registrar el usuario: {str(e)}")  # Opcional: Imprimir el error en la consola
        finally:
            cursor.close()
            conn.close()

        # Redirigir a la página de administración
        return redirect(url_for('admin'))


@app.route('/inscripcion', methods=['GET', 'POST'])
def inscripcion():
    if request.method == 'POST':
        # Obtener los datos del formulario
        nombre = request.form['nombre']
        apellido_paterno = request.form['apellido_paterno']
        apellido_materno = request.form['apellido_materno']
        escuela_inscripcion = request.form['escuela_inscripcion']
        nivel = request.form['nivel']
        grado = request.form['grado']
        curp = request.form['curp']
        fecha_nacimiento = request.form['fecha_nacimiento']
        alergias = request.form['alergias']
        capilla = request.form['capilla']
        beca = request.form['beca']
        sexo = request.form['Sexo']
        tipo_sangre = request.form['tipo_sangre']

        # Información familiar
        familia_existente = 'id_familia' in request.form
        if familia_existente:
            id_familia = request.form['id_familia']
        else:
            tutor = request.form['tutor']
            tel_emergencia = request.form['tel_emergencia']

        # Conectar a la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Insertar la familia si no existe
            if not familia_existente:
                cursor.execute(
                    "INSERT INTO familias (tutor, tel_emergencia) VALUES (%s, %s) RETURNING id_familia",
                    (tutor, tel_emergencia)
                )
                id_familia = cursor.fetchone()[0]

            # Insertar los datos del alumno
            cursor.execute(
                "INSERT INTO alumnos (nombre, apellido_paterno, apellido_materno, escuela_inscripcion, nivel, grado, curp, fecha_nacimiento, alergias, capilla, beca, sexo, tipo_sangre, id_familia) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (nombre, apellido_paterno, apellido_materno, escuela_inscripcion, nivel, grado, curp, fecha_nacimiento, alergias, capilla, beca, sexo, tipo_sangre, id_familia)
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

    # Si es GET, mostrar el formulario de inscripción
    return render_template('inscripcion.html')


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

        if user and password == user[-1]:  # user[-1] es la columna de la contraseña sin encriptar
            print("User:", user[-2])
            print("Password:", password)
            # Redirigir según el rol
            if user[-2] == 'admin':
                return redirect(url_for('admin'))
            elif user[-2] == 'profesor':
                return redirect(url_for('profesor'))
            elif user[-2] == 'director':
                return redirect(url_for('director'))
            else:
                return "Rol desconocido", 400  # Agregado para capturar cualquier rol no esperado
        else:
            return "Correo o contraseña incorrectos", 401
        
    return render_template('login.html')

'''
        if user and bcrypt.checkpw(password.encode('utf-8'), user[-1].encode('utf-8')):  # user[2] es la columna de la contraseña encriptada
            # Redirigir según el rol
            if user[-2] == 'administrativo':
                return redirect(url_for('admin'))
            elif user[-2] == 'maestro':
                return redirect(url_for('profesor'))
            elif user[-2] == 'direccion':
                return redirect(url_for('director'))
            
        else:
            return "Correo o contraseña incorrectos", 401

'''

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/profesor')
def profesor():
    return render_template('profesor.html')

@app.route('/director')
def director():
    return render_template('director.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
