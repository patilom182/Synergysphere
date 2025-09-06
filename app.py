import os
import json
from datetime import datetime
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, current_user, logout_user, login_required, UserMixin
from dotenv import load_dotenv

# --- Initialization and Config ---
load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_very_secret_key_for_sessions'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# --- Gemini API Configuration ---
try:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
except Exception as e:
    print(f"Error configuring Gemini API: {e}")
    model = None

# --- Login Manager Setup ---
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Database Models ---
project_members = db.Table('project_members',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('project_id', db.Integer, db.ForeignKey('project.id'), primary_key=True)
)
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='Developer')
    projects = db.relationship('Project', secondary=project_members, backref='members', lazy='dynamic')
    tasks = db.relationship('Task', backref='assignee', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    tags = db.Column(db.String(200), nullable=True)
    deadline = db.Column(db.Date, nullable=True)
    priority = db.Column(db.String(20), nullable=True)
    tasks = db.relationship('Task', backref='project', lazy=True, cascade="all, delete-orphan")
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='To Do')
    priority = db.Column(db.Integer, nullable=False, default=50)
    due_date = db.Column(db.Date, nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    assignee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    comments = db.relationship('Comment', backref='task', lazy=True, cascade="all, delete-orphan")
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)

# --- Main Routes ---
@app.route('/')
def index():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    return redirect(url_for('login'))
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        user_exists = User.query.filter_by(username=username).first()
        if user_exists:
            flash('Username already exists.', 'danger'); return redirect(url_for('login'))
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(username=username, password=hashed_password, role=role)
        db.session.add(new_user); db.session.commit()
        flash('Your account has been created! You are now able to log in.', 'success')
        return redirect(url_for('login'))
    return render_template('login.html')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user, remember=True); return redirect(url_for('dashboard'))
        else:
            flash('Login Unsuccessful. Please check username and password.', 'danger')
    return render_template('login.html')
@app.route('/logout')
def logout():
    logout_user(); return redirect(url_for('login'))
@app.route('/dashboard')
@login_required
def dashboard():
    projects = current_user.projects.order_by(Project.id.desc()).all()
    return render_template('dashboard.html', projects=projects)
@app.route('/project/new', methods=['GET', 'POST'])
@login_required
def create_project():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        tags = request.form.get('tags')
        priority = request.form.get('priority')
        deadline_str = request.form.get('deadline')
        deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date() if deadline_str else None
        new_project = Project(name=name, description=description, tags=tags, priority=priority, deadline=deadline)
        new_project.members.append(current_user)
        db.session.add(new_project); db.session.commit()
        flash(f"Project '{name}' created successfully!", 'success')
        return redirect(url_for('dashboard'))
    return render_template('create_project.html')
@app.route('/invite_user', methods=['POST'])
@login_required
def invite_user():
    username_to_invite = request.form.get('username')
    project_id = request.form.get('project_id')
    user_to_invite = User.query.filter_by(username=username_to_invite).first()
    project = Project.query.get(project_id)
    if not user_to_invite:
        flash(f"User '{username_to_invite}' not found.", 'danger')
    elif not project:
        flash('Project not found.', 'danger')
    elif user_to_invite in project.members:
        flash(f"User '{username_to_invite}' is already in the project.", 'info')
    else:
        project.members.append(user_to_invite); db.session.commit()
        flash(f"Successfully invited '{username_to_invite}' to the project!", 'success')
    return redirect(url_for('project_board', project_id=project_id))
@app.route('/project/<int:project_id>')
@login_required
def project_board(project_id):
    project = Project.query.get_or_404(project_id)
    if current_user not in project.members:
        flash("You are not a member of this project.", "danger"); return redirect(url_for('dashboard'))
    tasks = Task.query.filter_by(project_id=project.id).all()
    return render_template('board.html', project=project, tasks=tasks)
@app.route('/add_task', methods=['POST'])
@login_required
def add_task():
    content = request.form.get('content')
    project_id = request.form.get('project_id')
    assignee_id = request.form.get('assignee_id')
    due_date_str = request.form.get('due_date')
    if not all([content, project_id, assignee_id, due_date_str]):
        flash('All fields are required to add a task.', 'danger')
    else:
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        new_task = Task(content=content, project_id=project_id, assignee_id=assignee_id, due_date=due_date)
        db.session.add(new_task); db.session.commit()
    return redirect(url_for('project_board', project_id=project_id))
@app.route('/move_task', methods=['POST'])
@login_required
def move_task():
    task_id = request.form.get('task_id'); new_status = request.form.get('new_status')
    task = Task.query.get(task_id)
    if task and current_user in task.project.members:
        task.status = new_status; db.session.commit()
    return redirect(url_for('project_board', project_id=task.project_id))
@app.route('/task/<int:task_id>')
@login_required
def task_detail(task_id):
    task = Task.query.get_or_404(task_id)
    if current_user not in task.project.members:
        flash("You do not have access to this task.", "danger"); return redirect(url_for('dashboard'))
    return render_template('task_detail.html', task=task)
@app.route('/task/<int:task_id>/add_comment', methods=['POST'])
@login_required
def add_comment(task_id):
    task = Task.query.get_or_404(task_id)
    if current_user not in task.project.members:
        flash("You cannot comment on this task.", "danger"); return redirect(url_for('dashboard'))
    content = request.form.get('content')
    if content:
        comment = Comment(content=content, user_id=current_user.id, task_id=task.id)
        db.session.add(comment); db.session.commit()
    return redirect(url_for('task_detail', task_id=task.id))
@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')
@app.route('/my_tasks')
@login_required
def my_tasks():
    tasks = Task.query.filter_by(assignee_id=current_user.id).order_by(Task.due_date.asc()).all()
    return render_template('my_tasks.html', tasks=tasks)

# --- AI Routes ---
@app.route('/get_ai_synergy/<int:project_id>')
@login_required
def get_ai_synergy(project_id):
    if not model: return jsonify({'error': 'AI model is not configured.'})
    project = Project.query.get_or_404(project_id)
    if current_user not in project.members: return jsonify({'error': 'Unauthorized access.'}), 403
    tasks_text = ""
    for task in project.tasks:
        assignee_name = task.assignee.username if task.assignee else "Unassigned"
        assignee_role = task.assignee.role if task.assignee else "N/A"
        tasks_text += f"- Task: '{task.content}', Status: '{task.status}', Assignee: '{assignee_name}' (Role: {assignee_role})\n"
    if not tasks_text: return jsonify({'analysis': 'There are no tasks to analyze.'})
    
    # THE FULL, CORRECT PROMPT IS NOW RESTORED
    prompt = f"""
    You are SynergyBot, an expert project management assistant.
    Analyze the following list of tasks for a project named "{project.name}".
    Provide a concise, actionable analysis focusing on FOUR key areas: Workload Balance, Potential Bottlenecks, Suggested Priorities, AND **Skill Mismatch**.
    A **Skill Mismatch** is a high-risk situation where a task is assigned to a user whose role is not appropriate for it. For example, a "Design" task assigned to a "Backend Developer" is a mismatch. Point these out clearly.
    Format your response in simple markdown.

    ### Project Task List
    {tasks_text}

    ### Analysis
    """
    try:
        response = model.generate_content(prompt)
        return jsonify({'analysis': response.text})
    except Exception as e:
        return jsonify({'error': f'Failed to get analysis from AI. Details: {e}'}), 500

@app.route('/project/<int:project_id>/priority')
@login_required
def priority_view(project_id):
    project = Project.query.get_or_404(project_id)
    if current_user not in project.members:
        flash("You are not a member of this project.", "danger"); return redirect(url_for('dashboard'))
    return render_template('priority.html', project=project)

@app.route('/calculate_priority/<int:project_id>')
@login_required
def calculate_priority(project_id):
    if not model: return jsonify({'error': 'AI model is not configured.'})
    project = Project.query.get_or_404(project_id)
    if current_user not in project.members: return jsonify({'error': 'Unauthorized access.'}), 403
    tasks_for_ai = []
    for task in project.tasks:
        if task.status != 'Done':
            tasks_for_ai.append({"task_id": task.id,"content": task.content, "assignee_username": task.assignee.username, "assignee_role": task.assignee.role})
    if not tasks_for_ai: return jsonify({'message': 'No active tasks to prioritize.'})

    # THIS PROMPT IS ALSO CORRECT AND COMPLETE
    prompt = f"""
    You are a world-class technical project manager responsible for prioritizing tasks for the project "{project.name}".
    Your goal is to assign a priority score from 1 (lowest) to 100 (highest) to each task.
    You MUST follow this Prioritization Rubric:
    1. **Foundation First:** Core backend and database tasks (like "create database", "setup server", "build API", "make backend") are the most critical blockers and must receive the highest priority scores (90-100).
    2. **Dependencies Matter:** Integration tasks (like "connect frontend to backend") MUST have a lower priority than the core tasks they depend on.
    3. **Features Last:** Specific user-facing features (like "payment gateway", "user profile page") should generally have a lower priority than the foundational backend work they rely on.
    4. **UI in Parallel:** UI/Frontend tasks can often be worked on in parallel to the backend, but their priority is secondary to critical backend blockers.

    Analyze these tasks based on the rubric:
    {json.dumps(tasks_for_ai, indent=2)}

    Your response MUST be ONLY a valid JSON array of objects. Each object must have two keys: "task_id" (integer) and "priority" (integer).
    Do not include any explanation, markdown, or any text outside of the JSON array.
    Example response format: [{{"task_id": 1, "priority": 95}}, {{"task_id": 2, "priority": 80}}]
    """
    try:
        response = model.generate_content(prompt)
        cleaned_response_text = response.text.strip().replace("```json", "").replace("```", "")
        priority_data = json.loads(cleaned_response_text)
        for item in priority_data:
            task = Task.query.get(item['task_id'])
            if task: task.priority = item['priority']
        db.session.commit()
        return jsonify({'message': 'Priorities calculated!', 'priorities': priority_data})
    except Exception as e:
        print(f"Error processing AI priority response: {e}")
        return jsonify({'error': f'Failed to calculate priorities. Details: {e}'}), 500

# --- Main Execution ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)