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
            # Redirigir según el rol
            if user[-2] == 'administrativo':
                return redirect(url_for('admin'))
            elif user[-2] == 'maestro':
                return redirect(url_for('profesor'))
            elif user[-2] == 'direccion':
                return redirect(url_for('director'))
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
    return "<h1>Rol: Administrativo</h1>"

@app.route('/profesor')
def teacher():
    return "<h1>Rol: Maestro</h1>"

@app.route('/director')
def director():
    return "<h1>Rol: Dirección</h1>"

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
