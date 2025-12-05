import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# CONFIGURAÇÕES DE AMBIENTE
# Pega a chave do ambiente ou usa uma padrão para testes locais
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'minha_chave_secreta_local')

# Configuração do Banco de Dados (SQLite local ou Postgres na nuvem)
database_url = os.environ.get('DATABASE_URL', 'sqlite:///crm.db')
# Correção necessária para o Render (postgres:// -> postgresql://)
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
db = SQLAlchemy(app)

# --- MODELOS (BD) ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    # Relacionamento com clientes
    clients = db.relationship('Client', backref='owner', lazy=True)

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False) # RF-002
    phone = db.Column(db.String(20), nullable=False) # RF-002
    tipo = db.Column(db.String(50), default='Lead')  # RF-004
    status = db.Column(db.String(50), default='Novo') # RF-009 (Etapa do Pipeline)
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
            flash('Email já cadastrado.')
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
    
    # RF-002: Cadastro Rápido
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        tipo = request.form.get('tipo', 'Lead')
        
        if name and phone:
            new_client = Client(name=name, phone=phone, tipo=tipo, user_id=session['user_id'])
            db.session.add(new_client)
            db.session.commit()
            flash('Cliente adicionado!')
        
        return redirect(url_for('dashboard'))

    user_clients = Client.query.filter_by(user_id=session['user_id']).all()
    return render_template('dashboard.html', clients=user_clients)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)