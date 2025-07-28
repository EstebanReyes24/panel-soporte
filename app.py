from flask import Flask, render_template, request, redirect, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash

import pandas as pd
import io

app = Flask(__name__)
app.secret_key = 'IMCADOM2025**'  # Cambia esto por una más fuerte en producción
import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///entregas.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)


# Modelo de Entrega actualizado
class Entrega(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.String(100), default=datetime.now().strftime("%Y-%m-%d %H:%M"))
    equipo = db.Column(db.String(100))
    tipo_equipo = db.Column(db.String(50))
    imei = db.Column(db.String(50))
    persona = db.Column(db.String(100))
    observaciones = db.Column(db.String(200))
    fecha_devolucion = db.Column(db.String(100))
    devuelto = db.Column(db.Boolean, default=False)
    archivo = db.Column(db.String(200))  # ✅ NUEVO: nombre del archivo adjunto

class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    usuario = db.Column(db.String(100), unique=True, nullable=False)
    contrasena_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.contrasena_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.contrasena_hash, password)


# Ruta principal con filtro por fecha y búsqueda

@app.route('/login', methods=['GET', 'POST'])  # ✅ SIN login_required AQUÍ
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        contrasena = request.form['contrasena']
        user = Usuario.query.filter_by(usuario=usuario).first()
        
        if user and user.check_password(contrasena):
            login_user(user)
            flash('Sesión iniciada correctamente', 'success')
            return redirect('/')
        else:
            flash('Usuario o contraseña incorrectos', 'danger')
    return render_template('login.html')
    

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    fecha_filtro = request.form.get('fecha')
    busqueda = request.form.get('busqueda', '').lower()
    query = Entrega.query.filter_by(devuelto=False)

    if fecha_filtro:
        query = query.filter(Entrega.fecha.like(f"{fecha_filtro}%"))
    if busqueda:
        query = query.filter(
            db.or_(
                Entrega.equipo.ilike(f"%{busqueda}%"),
                Entrega.tipo_equipo.ilike(f"%{busqueda}%"),
                Entrega.persona.ilike(f"%{busqueda}%"),
                Entrega.imei.ilike(f"%{busqueda}%")
            )
        )

    entregas = query.order_by(Entrega.id.desc()).all()
    return render_template('index.html', entregas=entregas)

# Guardar nueva entrega
# Guardar nueva entrega

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada', 'info')
    return redirect('/login')

@app.route('/registrar', methods=['GET', 'POST'])
def registrar():
    if request.method == 'POST':
        nombre = request.form['nombre']
        usuario = request.form['usuario']
        contrasena = request.form['contrasena']

        if Usuario.query.filter_by(usuario=usuario).first():
            flash("Ese nombre de usuario ya está registrado", "danger")
            return redirect('/registrar')

        nuevo_usuario = Usuario(nombre=nombre, usuario=usuario)
        nuevo_usuario.set_password(contrasena)
        db.session.add(nuevo_usuario)
        db.session.commit()
       return redirect('/')

    return render_template('registrar.html')


@app.route('/guardar', methods=['POST'])
@login_required
def guardar_entrega():
    equipo = request.form['equipo']
    tipo_equipo = request.form['tipo_equipo']
    imei = request.form.get('imei')
    persona = request.form['persona']
    observaciones = request.form['observaciones']

    archivo = request.files['archivo']
    nombre_archivo = None
    if archivo and archivo.filename:
        nombre_archivo = secure_filename(archivo.filename)
        archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], nombre_archivo))

    nueva_entrega = Entrega(
        equipo=equipo,
        tipo_equipo=tipo_equipo,
        imei=imei,
        persona=persona,
        observaciones=observaciones,
        archivo=nombre_archivo
    )
    db.session.add(nueva_entrega)
    db.session.commit()
    
    flash("Entrega registrada exitosamente", "success")  # ✅ CORRECTO DENTRO
    return redirect('/')

# Editar entrega

@app.route('/editar/<int:id>')
@login_required
def editar(id):
    entrega = Entrega.query.get_or_404(id)
    return render_template('editar.html', entrega=entrega)


@app.route('/actualizar/<int:id>', methods=['POST'])
@login_required
def actualizar(id):
    entrega = Entrega.query.get_or_404(id)
    entrega.equipo = request.form['equipo']
    entrega.tipo_equipo = request.form['tipo_equipo']
    entrega.imei = request.form.get('imei')
    entrega.persona = request.form['persona']
    entrega.observaciones = request.form['observaciones']
    db.session.commit()
    
    flash("Entrega actualizada correctamente", "info")  # ✅ CORREGIDO
    return redirect('/')

# Eliminar

@app.route('/eliminar/<int:id>')
@login_required
def eliminar(id):
    entrega = Entrega.query.get_or_404(id)
    db.session.delete(entrega)
    db.session.commit()
    return redirect('/')

# Exportar

@app.route('/exportar')
@login_required
def exportar():
    entregas = Entrega.query.order_by(Entrega.id.desc()).all()
    data = [{
        "Fecha": e.fecha,
        "Equipo": e.equipo,
        "Tipo": e.tipo_equipo,
        "IMEI": e.imei,
        "Entregado a": e.persona,
        "Observaciones": e.observaciones
    } for e in entregas]
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Entregas')
    output.seek(0)
    return send_file(output, download_name="entregas.xlsx", as_attachment=True)


@app.route('/devolver/<int:id>')
@login_required
def devolver(id):
    entrega = Entrega.query.get_or_404(id)
    entrega.devuelto = True
    entrega.fecha_devolucion = datetime.now().strftime("%Y-%m-%d %H:%M")
    db.session.commit()
    return redirect('/')


@app.route('/devueltos')
@login_required
def devueltos():
    entregas = Entrega.query.filter_by(devuelto=True).order_by(Entrega.id.desc()).all()
    return render_template('devueltos.html', entregas=entregas)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
