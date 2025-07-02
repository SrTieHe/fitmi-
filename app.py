# fitmi_plus_app/app.py
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, UTC # Importar UTC para DeprecationWarning

# Inicializa o aplicativo Flask
app = Flask(__name__)

# Configurações do aplicativo
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'sua_chave_secreta_muito_segura_aqui')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fitmiplus.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializa o SQLAlchemy para interagir com o banco de dados
db = SQLAlchemy(app)

# Inicializa o Flask-Login para gerenciar sessões de usuário
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# =============================================================================
# Context Processor para tornar 'datetime' e 'current_user' disponíveis nos templates
# =============================================================================
@app.context_processor
def inject_global_vars():
    """Injeta o objeto datetime e a função current_user nos templates."""
    return {'datetime': datetime, 'current_user': current_user}


# =============================================================================
# Modelos do Banco de Dados (SQLAlchemy ORM)
# =============================================================================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='patient')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    patient_profile = db.relationship('Patient', backref='user', uselist=False)
    nutritionist_profile = db.relationship('Nutritionist', backref='user', uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date)
    # Adicione mais campos específicos do paciente aqui (ex: peso, altura, histórico)

    meal_plans = db.relationship('MealPlan', backref='patient', lazy=True)
    food_diary_entries = db.relationship('FoodDiaryEntry', backref='patient', lazy=True)
    appointments = db.relationship('Appointment', backref='patient', lazy=True)

    def __repr__(self):
        return f'<Patient {self.full_name}>'

class Nutritionist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    crm_nutri = db.Column(db.String(50), unique=True, nullable=False)
    specialty = db.Column(db.String(100))
    bio = db.Column(db.Text)

    patients = db.relationship('Patient', secondary='nutritionist_patient_association', backref='nutritionists', lazy=True)
    courses = db.relationship('Course', backref='nutritionist', lazy=True)
    appointments = db.relationship('Appointment', backref='nutritionist', lazy=True)

    def __repr__(self):
        return f'<Nutritionist {self.full_name}>'

nutritionist_patient_association = db.Table(
    'nutritionist_patient_association',
    db.Column('nutritionist_id', db.Integer, db.ForeignKey('nutritionist.id'), primary_key=True),
    db.Column('patient_id', db.Integer, db.ForeignKey('patient.id'), primary_key=True)
)

class FoodItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    calories = db.Column(db.Float)
    protein = db.Column(db.Float)
    carbohydrates = db.Column(db.Float)
    fats = db.Column(db.Float)
    source = db.Column(db.String(50))

    def __repr__(self):
        return f'<FoodItem {self.name}>'

class MealPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    meals = db.relationship('Meal', backref='meal_plan', lazy=True)

    def __repr__(self):
        return f'<MealPlan {self.name} for Patient {self.patient_id}>'

class Meal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    meal_plan_id = db.Column(db.Integer, db.ForeignKey('meal_plan.id'), nullable=False)
    meal_type = db.Column(db.String(50), nullable=False)
    time = db.Column(db.Time)
    notes = db.Column(db.Text)

    meal_items = db.relationship('MealItem', backref='meal', lazy=True)

    def __repr__(self):
        return f'<Meal {self.meal_type} in MealPlan {self.meal_plan_id}>'

class MealItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    meal_id = db.Column(db.Integer, db.ForeignKey('meal.id'), nullable=False)
    food_item_id = db.Column(db.Integer, db.ForeignKey('food_item.id'), nullable=False)
    quantity_grams = db.Column(db.Float)
    notes = db.Column(db.String(200))

    food_item = db.relationship('FoodItem')

    def __repr__(self):
        return f'<MealItem {self.food_item.name} in Meal {self.meal_id}>'

class FoodDiaryEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    food_item_id = db.Column(db.Integer, db.ForeignKey('food_item.id'), nullable=False)
    quantity_grams = db.Column(db.Float, nullable=False)
    meal_type = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.now(UTC).date())
    time = db.Column(db.Time, nullable=False, default=datetime.now(UTC).time())
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    food_item = db.relationship('FoodItem')

    def __repr__(self):
        return f'<FoodDiaryEntry Patient {self.patient_id} - {self.food_item.name} on {self.date}>'

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    nutritionist_id = db.Column(db.Integer, db.ForeignKey('nutritionist.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='scheduled')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Appointment {self.id} - {self.start_time} with Nutri {self.nutritionist_id}>'

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nutritionist_id = db.Column(db.Integer, db.ForeignKey('nutritionist.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, default=0.0)
    is_certified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    modules = db.relationship('CourseModule', backref='course', lazy=True)

    def __repr__(self):
        return f'<Course {self.title}>'

class CourseModule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    order = db.Column(db.Integer)
    is_limited_content = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<CourseModule {self.title} in Course {self.course_id}>'

# =============================================================================
# Funções de Carregamento de Usuário para Flask-Login
# =============================================================================

@login_manager.user_loader
def load_user(user_id):
    """
    Esta função é usada pelo Flask-Login para recarregar o objeto User da sessão.
    É essencial que esta função esteja definida e decorada corretamente.
    """
    print(f"DEBUG: load_user chamado para user_id: {user_id}")
    return User.query.get(int(user_id))

# =============================================================================
# Rotas (Endpoints da Aplicação Web)
# =============================================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    # Verifica se há um nutri_id na URL para pré-selecionar o nutricionista
    nutri_id = request.args.get('nutri_id', type=int)
    nutritionist = None
    if nutri_id:
        nutritionist = Nutritionist.query.get(nutri_id)
        if not nutritionist:
            flash('Nutricionista não encontrado para o link de convite.', 'danger')
            nutri_id = None # Limpa o ID se não for válido

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'patient')
        # Pega o nutri_id do formulário (se veio de um link de convite)
        form_nutri_id = request.form.get('nutri_id', type=int)

        if not username or not email or not password:
            flash('Por favor, preencha todos os campos.', 'danger')
            return redirect(url_for('register', nutri_id=form_nutri_id if form_nutri_id else ''))

        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Nome de usuário ou e-mail já cadastrado.', 'danger')
            return redirect(url_for('register', nutri_id=form_nutri_id if form_nutri_id else ''))

        new_user = User(username=username, email=email, role=role)
        new_user.set_password(password)

        try:
            db.session.add(new_user)
            db.session.commit()

            if role == 'patient':
                patient_name = request.form.get('full_name')
                new_patient = Patient(user_id=new_user.id, full_name=patient_name or username)
                db.session.add(new_patient)
                db.session.commit() # Salva o paciente para ter um ID

                # Se o paciente se registrou via link de convite de um nutricionista
                if form_nutri_id:
                    target_nutritionist = Nutritionist.query.get(form_nutri_id)
                    if target_nutritionist:
                        # Verifica se a associação já existe para evitar duplicatas
                        if new_patient not in target_nutritionist.patients:
                            target_nutritionist.patients.append(new_patient)
                            db.session.commit()
                            flash(f'Você foi associado(a) ao nutricionista {target_nutritionist.full_name}.', 'info')
                        else:
                            flash('Você já está associado(a) a este nutricionista.', 'info')
            elif role == 'nutritionist':
                nutritionist_name = request.form.get('full_name')
                crm_nutri = request.form.get('crm_nutri')
                if not crm_nutri:
                    flash('Por favor, forneça o CRM do nutricionista.', 'danger')
                    db.session.rollback()
                    return redirect(url_for('register', nutri_id=form_nutri_id if form_nutri_id else ''))
                new_nutritionist = Nutritionist(user_id=new_user.id, full_name=nutritionist_name or username, crm_nutri=crm_nutri)
                db.session.add(new_nutritionist)
                db.session.commit()

            flash('Registro realizado com sucesso! Por favor, faça login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ocorreu um erro ao registrar: {e}', 'danger')
            return redirect(url_for('register', nutri_id=form_nutri_id if form_nutri_id else ''))

    return render_template('register.html', nutri_id=nutri_id, nutritionist=nutritionist)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'patient':
            return redirect(url_for('patient_dashboard'))
        elif current_user.role == 'nutritionist':
            return redirect(url_for('nutritionist_dashboard'))
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash('Email ou senha inválidos. Tente novamente.', 'danger')
            return redirect(url_for('login'))

        login_user(user, remember=remember)
        flash(f'Bem-vindo(a), {user.username}!', 'success')

        if user.role == 'patient':
            return redirect(url_for('patient_dashboard'))
        elif user.role == 'nutritionist':
            return redirect(url_for('nutritionist_dashboard'))
        else:
            return redirect(url_for('index'))

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você foi desconectado(a).', 'info')
    return redirect(url_for('index'))

@app.route('/patient_dashboard')
@login_required
def patient_dashboard():
    if current_user.role != 'patient':
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('index'))

    patient = Patient.query.filter_by(user_id=current_user.id).first()
    if not patient:
        flash('Perfil de paciente não encontrado.', 'danger')
        return redirect(url_for('index'))

    return render_template('patient_dashboard.html', patient=patient)

@app.route('/nutritionist_dashboard')
@login_required
def nutritionist_dashboard():
    if current_user.role != 'nutritionist':
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('index'))

    nutritionist = Nutritionist.query.filter_by(user_id=current_user.id).first()
    if not nutritionist:
        flash('Perfil de nutricionista não encontrado.', 'danger')
        return redirect(url_for('index'))

    # Geração do link de convite para o nutricionista
    invite_link = url_for('register', nutri_id=nutritionist.id, _external=True)

    return render_template('nutritionist_dashboard.html', nutritionist=nutritionist, invite_link=invite_link)


@app.route('/patients') # Rota para a lista de pacientes
@login_required
def patients():
    if current_user.role != 'nutritionist':
        flash('Acesso não autorizado. Apenas nutricionistas podem ver pacientes.', 'danger')
        return redirect(url_for('index'))

    nutritionist = Nutritionist.query.filter_by(user_id=current_user.id).first()
    if not nutritionist:
        flash('Perfil de nutricionista não encontrado.', 'danger')
        return redirect(url_for('index'))

    # Carrega os pacientes associados a este nutricionista
    patients_list = nutritionist.patients
    # Passa o objeto nutritionist para o template
    return render_template('patients.html', patients=patients_list, nutritionist=nutritionist)


@app.route('/add_patient', methods=['GET', 'POST'])
@login_required
def add_patient():
    if current_user.role != 'nutritionist':
        flash('Acesso não autorizado. Apenas nutricionistas podem adicionar pacientes.', 'danger')
        return redirect(url_for('index'))

    nutritionist = Nutritionist.query.filter_by(user_id=current_user.id).first()
    if not nutritionist:
        flash('Perfil de nutricionista não encontrado.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')

        if not username or not email or not password or not full_name:
            flash('Por favor, preencha todos os campos.', 'danger')
            return redirect(url_for('add_patient'))

        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Nome de usuário ou e-mail já cadastrado.', 'danger')
            return redirect(url_for('add_patient'))

        try:
            # Cria o novo usuário (paciente)
            new_user = User(username=username, email=email, role='patient')
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()

            # Cria o perfil do paciente
            new_patient = Patient(user_id=new_user.id, full_name=full_name)
            db.session.add(new_patient)
            db.session.commit()

            # Associa o paciente ao nutricionista logado
            nutritionist.patients.append(new_patient)
            db.session.commit()

            flash(f'Paciente {full_name} adicionado e associado com sucesso!', 'success')
            return redirect(url_for('patients')) # Redireciona para a lista de pacientes
        except Exception as e:
            db.session.rollback()
            flash(f'Ocorreu um erro ao adicionar o paciente: {e}', 'danger')
            return redirect(url_for('add_patient'))

    return render_template('add_patient.html')


@app.route('/food_items')
@login_required
def food_items():
    all_food_items = FoodItem.query.all()
    return render_template('food_items.html', food_items=all_food_items)

@app.route('/add_food_item', methods=['GET', 'POST'])
@login_required
def add_food_item():
    if current_user.role != 'nutritionist':
        flash('Acesso não autorizado para adicionar alimentos.', 'danger')
        return redirect(url_for('food_items'))

    if request.method == 'POST':
        name = request.form.get('name')
        calories = request.form.get('calories')
        protein = request.form.get('protein')
        carbohydrates = request.form.get('carbohydrates')
        fats = request.form.get('fats')
        source = request.form.get('source')

        if not name or not calories:
            flash('Nome e calorias são obrigatórios.', 'danger')
            return redirect(url_for('add_food_item'))

        try:
            new_food = FoodItem(
                name=name,
                calories=float(calories),
                protein=float(protein) if protein else 0.0,
                carbohydrates=float(carbohydrates) if carbohydrates else 0.0,
                fats=float(fats) if fats else 0.0,
                source=source
            )
            db.session.add(new_food)
            db.session.commit()
            flash('Alimento adicionado com sucesso!', 'success')
            return redirect(url_for('food_items'))
        except ValueError:
            flash('Por favor, insira valores numéricos válidos para os nutrientes.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao adicionar alimento: {e}', 'danger')
    return render_template('add_food_item.html')


@app.route('/appointments')
@login_required
def appointments():
    if current_user.role == 'patient':
        patient = Patient.query.filter_by(user_id=current_user.id).first()
        if not patient:
            flash('Perfil de paciente não encontrado.', 'danger')
            return redirect(url_for('index'))
        user_appointments = Appointment.query.filter_by(patient_id=patient.id).order_by(Appointment.start_time.asc()).all()
    elif current_user.role == 'nutritionist':
        nutritionist = Nutritionist.query.filter_by(user_id=current_user.id).first()
        if not nutritionist:
            flash('Perfil de nutricionista não encontrado.', 'danger')
            return redirect(url_for('index'))
        user_appointments = Appointment.query.filter_by(nutritionist_id=nutritionist.id).order_by(Appointment.start_time.asc()).all()
    else:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('index'))

    return render_template('appointments.html', appointments=user_appointments)

@app.route('/schedule_appointment', methods=['GET', 'POST'])
@login_required
def schedule_appointment():
    if current_user.role != 'patient':
        flash('Apenas pacientes podem agendar consultas.', 'danger')
        return redirect(url_for('index'))

    patient = Patient.query.filter_by(user_id=current_user.id).first()
    if not patient:
        flash('Perfil de paciente não encontrado.', 'danger')
        return redirect(url_for('index'))

    nutritionists = Nutritionist.query.all()

    if request.method == 'POST':
        nutritionist_id = request.form.get('nutritionist_id')
        date_str = request.form.get('appointment_date')
        time_str = request.form.get('appointment_time')

        if not nutritionist_id or not date_str or not time_str:
            flash('Por favor, preencha todos os campos.', 'danger')
            return redirect(url_for('schedule_appointment'))

        try:
            appointment_datetime_str = f"{date_str} {time_str}"
            start_time = datetime.strptime(appointment_datetime_str, '%Y-%m-%d %H:%M')
            end_time = start_time + timedelta(hours=1)

            new_appointment = Appointment(
                patient_id=patient.id,
                nutritionist_id=nutritionist_id,
                start_time=start_time,
                end_time=end_time,
                status='scheduled'
            )
            db.session.add(new_appointment)
            db.session.commit()
            flash('Consulta agendada com sucesso!', 'success')
            return redirect(url_for('appointments'))
        except ValueError:
            flash('Formato de data/hora inválido.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao agendar consulta: {e}', 'danger')

    return render_template('schedule_appointment.html', nutritionists=nutritionists)

# =============================================================================
# Configuração para rodar o aplicativo
# =============================================================================

with app.app_context():
    db.create_all()
    if not FoodItem.query.first():
        sample_foods = [
            FoodItem(name='Maçã', calories=52.0, protein=0.3, carbohydrates=14.0, fats=0.2, source='USDA'),
            FoodItem(name='Frango Grelhado (100g)', calories=165.0, protein=31.0, carbohydrates=0.0, fats=3.6, source='USDA'),
            FoodItem(name='Arroz Branco Cozido (100g)', calories=130.0, protein=2.7, carbohydrates=28.0, fats=0.3, source='TACO'),
            FoodItem(name='Brócolis Cozido (100g)', calories=34.0, protein=2.8, carbohydrates=6.6, fats=0.4, source='USDA'),
            FoodItem(name='Ovo Cozido (unidade)', calories=78.0, protein=6.0, carbohydrates=0.6, fats=5.3, source='USDA')
        ]
        db.session.bulk_save_objects(sample_foods)
        db.session.commit()
        print("Alimentos de exemplo adicionados ao banco de dados.")

if __name__ == '__main__':
    app.run(debug=True)
