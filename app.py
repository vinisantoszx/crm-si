import os
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
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
    tipo = db.Column(db.String(50), default='Lead') 
    value = db.Column(db.Float, default=0.0) 
    status = db.Column(db.String(50), default='Lead') 
    # RF-009: Data para permitir filtros de período no dashboard
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
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
    
    # Lógica de Salvar Novo Cliente
    if request.method == 'POST' and 'name' in request.form:
        name = request.form.get('name')
        phone = request.form.get('phone')
        value = request.form.get('value', 0)
        try:
            value = float(value)
        except ValueError:
            value = 0.0
        
        if name and phone:
            new_client = Client(name=name, phone=phone, value=value, status='Lead', user_id=session['user_id'])
            db.session.add(new_client)
            db.session.commit()
            flash('Cliente adicionado com sucesso!')
        return redirect(url_for('dashboard'))

    # --- RF-009: FILTROS DE DATA ---
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')

    query = Client.query.filter_by(user_id=session['user_id'])

    # Se houver filtro, aplica na query
    if data_inicio and data_fim:
        try:
            d_ini = datetime.strptime(data_inicio, '%Y-%m-%d')
            d_fim = datetime.strptime(data_fim, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query = query.filter(Client.created_at >= d_ini, Client.created_at <= d_fim)
        except ValueError:
            pass # Se data inválida, ignora
            
    all_clients_filtered = query.all()
    
    # --- CÁLCULO DOS DADOS REAIS (KPIS) ---
    
    total_volume = sum(c.value for c in all_clients_filtered)
    
    fechados = [c for c in all_clients_filtered if c.status == 'Fechado']
    total_fechado = sum(c.value for c in fechados)
    count_fechado = len(fechados)
    
    count_active = len([c for c in all_clients_filtered if c.status != 'Fechado'])

    ticket_medio = 0
    if count_fechado > 0:
        ticket_medio = total_fechado / count_fechado

    taxa_conversao = 0
    total_clientes_count = len(all_clients_filtered)
    if total_clientes_count > 0:
        taxa_conversao = (count_fechado / total_clientes_count) * 100

    kpis = {
        'volume': f"{total_volume:,.2f}",
        'fechado': f"{total_fechado:,.2f}",
        'ativos': count_active,
        'ticket_medio': f"{ticket_medio:,.2f}",
        'conversao': int(taxa_conversao)
    }

    return render_template('dashboard.html', clients=all_clients_filtered, kpis=kpis, filtro_ini=data_inicio, filtro_fim=data_fim)

@app.route('/oportunidades')
def oportunidades():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    clients = Client.query.filter_by(user_id=session['user_id']).all()
    
    resumo = {
        'Lead': sum(c.value for c in clients if c.status == 'Lead'),
        'Qualificado': sum(c.value for c in clients if c.status == 'Qualificado'),
        'Proposta': sum(c.value for c in clients if c.status == 'Proposta'),
        'Negociacao': sum(c.value for c in clients if c.status == 'Negociacao'),
        'Fechado': sum(c.value for c in clients if c.status == 'Fechado')
    }
    
    contagem = {
        'Lead': len([c for c in clients if c.status == 'Lead']),
        'Qualificado': len([c for c in clients if c.status == 'Qualificado']),
        'Proposta': len([c for c in clients if c.status == 'Proposta']),
        'Negociacao': len([c for c in clients if c.status == 'Negociacao']),
        'Fechado': len([c for c in clients if c.status == 'Fechado'])
    }

    return render_template('oportunidades.html', clients=clients, resumo=resumo, contagem=contagem)

@app.route('/clientes')
def clientes():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    filtro_status = request.args.get('filtro')
    query = Client.query.filter_by(user_id=session['user_id'])
    
    if filtro_status and filtro_status != 'Todos':
        if filtro_status == 'Ativos':
            query = query.filter(Client.status.in_(['Lead', 'Qualificado', 'Proposta', 'Negociacao']))
        elif filtro_status == 'Fechados':
            query = query.filter_by(status='Fechado')
        else:
            query = query.filter_by(status=filtro_status)
            
    clients = query.all()
    return render_template('clientes.html', clients=clients, filtro_atual=filtro_status)

# Rota Legada (Mantida para compatibilidade)
@app.route('/update_status/<int:id>/<string:new_status>')
def update_status(id, new_status):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    client = Client.query.get_or_404(id)
    if client.user_id == session['user_id']:
        client.status = new_status
        db.session.commit()
        flash(f'Cliente movido para {new_status}!')
    return redirect(url_for('dashboard'))

# --- RF-005: Rota AJAX para o Drag & Drop ---
@app.route('/api/update_kanban', methods=['POST'])
def api_update_kanban():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    client_id = data.get('client_id')
    new_status = data.get('new_status')
    
    client = Client.query.get(client_id)
    
    if client and client.user_id == session['user_id']:
        client.status = new_status
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'error': 'Cliente não encontrado'}), 404

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)