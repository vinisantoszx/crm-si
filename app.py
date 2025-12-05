import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# CONFIGURAÇÕES
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_123')
database_url = os.environ.get('DATABASE_URL', 'sqlite:///crm.db')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
db = SQLAlchemy(app)

# --- MODELOS ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    clients = db.relationship('Client', backref='owner', lazy=True)

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    tipo = db.Column(db.String(50), default='Lead') # RF-004
    # RF-007: Atributos da Oportunidade (Valor Monetário)
    value = db.Column(db.Float, default=0.0) 
    # RF-009: Status para o Kanban (Lead -> Negociação -> Fechado)
    status = db.Column(db.String(50), default='Lead') 
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# --- ROTAS ---

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if User.query.filter_by(email=email).first():
            flash('Email já existe.')
            return redirect(url_for('register'))
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(email=email, password_hash=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        flash('Conta criada! Faça login.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        else:
            flash('Login inválido.')
    return render_template('login.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # RF-002: Cadastro Rápido de Clientes
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        value = request.form.get('value', 0) # RF-007
        
        try:
            value = float(value)
        except ValueError:
            value = 0.0

        if name and phone:
            # Todo novo cliente entra como 'Lead' no Kanban
            new_client = Client(name=name, phone=phone, value=value, status='Lead', user_id=session['user_id'])
            db.session.add(new_client)
            db.session.commit()
            flash('Oportunidade adicionada!')
        
        return redirect(url_for('dashboard'))

    # Busca clientes do usuário
    all_clients = Client.query.filter_by(user_id=session['user_id']).all()
    
    # RF-012/013: Indicadores (KPIs)
    total_volume = sum(c.value for c in all_clients)
    total_fechado = sum(c.value for c in all_clients if c.status == 'Fechado')
    count_active = len([c for c in all_clients if c.status != 'Fechado'])

    return render_template('dashboard.html', 
                           clients=all_clients, 
                           total_volume=total_volume,
                           total_fechado=total_fechado,
                           count_active=count_active)

# Nova Rota para Mover Cards no Kanban (RF-009)
@app.route('/update_status/<int:id>/<string:new_status>')
def update_status(id, new_status):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    client = Client.query.get_or_404(id)
    
    # Segurança: Garante que o cliente pertence ao usuário logado
    if client.user_id == session['user_id']:
        client.status = new_status
        db.session.commit()
        flash(f'Cliente movido para {new_status}!')
    
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

# Força criação das tabelas no Render
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)