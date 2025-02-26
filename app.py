from flask import Flask, render_template, request, redirect, url_for
from flask_mysqldb import MySQL
import bcrypt

app = Flask(__name__, template_folder='templates')

# Configuración de la base de datos
app.config['MYSQL_HOST'] = 'http://dpg-cuvnkjtds78s73co00gg-a.oregon-postgres.render.com'
app.config['MYSQL_USER'] = 'neoschool_db_user'  # Asegúrate de tener el usuario adecuado
app.config['MYSQL_PASSWORD'] = '9UJKJWvgdvOC5bT2fuu9y3fan5DvD9Wz'  # Añadir la contraseña de la base de datos
app.config['MYSQL_DB'] = 'neoschool_db'

mysql = MySQL(app)

@app.route('/')
def home():
    return render_template('Index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user and bcrypt.checkpw(password.encode('utf-8'), user[2].encode('utf-8')):  # user[2] es la columna de la contraseña encriptada
            # Redirigir según el rol
            if user[3] == 'administrativo':
                return redirect(url_for('admin'))
            elif user[3] == 'maestro':
                return redirect(url_for('teacher'))
            elif user[3] == 'direccion':
                return redirect(url_for('director'))
        else:
            return "Correo o contraseña incorrectos", 401

    return render_template('login.html')

@app.route('/admin')
def admin():
    return "<h1>Rol: Administrativo</h1>"

@app.route('/teacher')
def teacher():
    return "<h1>Rol: Maestro</h1>"

@app.route('/director')
def director():
    return "<h1>Rol: Dirección</h1>"

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
