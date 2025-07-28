from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from functools import wraps
import os
import csv
import pandas as pd
import io
from markupsafe import Markup
import pickle
import re
from flask import send_file, flash

from flask_mail import Mail, Message
app = Flask(__name__)  # ✅ Define app first
app.secret_key = 'mySuperSecretKey123!'


# Email config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'tasbihaashraf32@gmail.com'  # 🔁 your Gmail
app.config['MAIL_PASSWORD'] = 'cdchuwmlpzanudlt'      # 🔁 app password (NOT Gmail login)
app.config['MAIL_DEFAULT_SENDER'] = 'tasbihaashraf32@gmail.com'

mail = Mail(app)


# Load your ML models
with open('classifier.pkl', 'rb') as f:
    classifier = pickle.load(f)

with open('vectorizer.pkl', 'rb') as f:
    vectorizer = pickle.load(f)

# Ambiguous word highlighter function
def highlight_ambiguous(text, ambiguous_words):
    if not ambiguous_words:
        return Markup.escape(text)

    for word_info in sorted(ambiguous_words, key=lambda w: w['start'], reverse=True):
        start = word_info['start']
        end = word_info['end']
        word = text[start:end]
        highlight = f'<span style="background-color: yellow; font-weight: bold;">{Markup.escape(word)}</span>'
        text = text[:start] + highlight + text[end:]

    return Markup(text)



# ---------- User Helpers ----------
USERS_CSV = 'users.csv'

def load_users():
    users = {}
    if os.path.exists(USERS_CSV):
        with open(USERS_CSV, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                users[row['email']] = {
                    'name': row['name'],
                    'password': row['password']
                }
    return users

def save_user_to_csv(name, email, password):
    file_exists = os.path.isfile(USERS_CSV)
    with open(USERS_CSV, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['name', 'email', 'password'])
        writer.writerow([name, email, password])

# ---------- Login Decorator ----------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash("Please login first.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ---------- Ambiguity Detection ----------
ambiguous_words = [
    "may", "might", "could", "should", "possibly", "some", "several", 
    "various", "usually", "often", "frequently", "approximately", "about",
    "near", "somewhat", "relatively", "adequate", "sufficient", "appropriate",
    "typically", "as needed", "as appropriate", "as soon as possible", "soon",
    "fast", "quick", "easy", "simple", "user-friendly", "intuitive", "efficient",
    "secure", "reliable", "robust", "flexible", "scalable", "maintainable"
]
def highlight_ambiguous(text, ambiguous_words):
    # Simple highlight logic
    for w in set(word['word'] for word in ambiguous_words):
        text = text.replace(w, f'<mark>{w}</mark>')
    return text

app.jinja_env.globals.update(highlight_ambiguous=highlight_ambiguous)

def detect_ambiguity(text):
    text_lower = text.lower()
    ambiguous_found = []

    for word in ambiguous_words:
        pattern = r'\b' + re.escape(word) + r'\b'
        if re.search(pattern, text_lower):
            if word == "should":
                if re.search(r'should.*\b(\d+|\d+\.\d+)\b', text_lower):
                    continue
            ambiguous_found.append(word)
    return ambiguous_found

# Analyze single requirement text
def analyze_requirement(text, vectorizer, classifier):
    X_vec = vectorizer.transform([text])
    prediction = classifier.predict(X_vec)[0]
    ambiguous_found = detect_ambiguity(text)
    ambiguous_pos = [
        {"word": w, "start": m.start(), "end": m.end()}
        for w in ambiguous_found
        for m in re.finditer(r'\b' + re.escape(w) + r'\b', text.lower())
    ]
    return {
        "requirement": text,
        "type": prediction,
        "ambiguous": bool(ambiguous_found),
        "ambiguous_words": ambiguous_pos
    }

# Save analyzed results to history.csv
def save_to_history(requirement, req_type, ambiguous, ambiguous_words):
    filename = 'history.csv'
    file_exists = os.path.isfile(filename)
    with open(filename, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['Requirement', 'Type', 'Ambiguity', 'Ambiguous Words'])
        ambiguous_words_str = ', '.join([w['word'] for w in ambiguous_words]) if ambiguous_words else ''
        writer.writerow([requirement, req_type, 'Yes' if ambiguous else 'No', ambiguous_words_str])

# ---------------- ROUTES ----------------

@app.route('/', endpoint='start_page')
def start_page():
    return render_template('start.html')



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').lower()
        password = request.form.get('password', '')
        users = load_users()
        user = users.get(email)
        if user and user['password'] == password:
            session['user'] = email
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for('analyzer'))
        else:
            flash("Invalid email or password.", "error")
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    name = request.form.get('name', '')
    email = request.form.get('email', '').lower()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')
    if not (name and email and password and confirm_password):
        flash("Please fill all the fields.", "error")
        return redirect(url_for('login'))
    if password != confirm_password:
        flash("Passwords do not match.", "error")
        return redirect(url_for('login'))
    users = load_users()
    if email in users:
        flash("Email already registered. Please login.", "error")
        return redirect(url_for('login'))
    save_user_to_csv(name, email, password)
    flash("Registration successful! Please login now.", "success")
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash("You have been logged out.", "success")
    return redirect(url_for('start_page'))

@app.route('/analyzer', methods=['GET', 'POST'])
@login_required
def analyzer():
    if request.method == 'POST':
        text = request.form.get('requirement')
        uploaded_file = request.files.get('file')

        if text and (not uploaded_file or uploaded_file.filename == ''):
            result = analyze_requirement(text, vectorizer, classifier)
            save_to_history(text, result['type'], result['ambiguous'], result['ambiguous_words'])
            users = load_users()
            user = users.get(session['user'])
            return render_template('index.html', statement=text, result=result, user=user)

        elif uploaded_file and uploaded_file.filename != '':
            filename = uploaded_file.filename
            ext = os.path.splitext(filename)[1].lower()

            if ext == '.csv':
                df = pd.read_csv(uploaded_file)
            elif ext in ['.xls', '.xlsx']:
                df = pd.read_excel(uploaded_file)
            else:
                flash("Unsupported file type.", "error")
                return redirect(url_for('index'))

            col = 'Requirement' if 'Requirement' in df.columns else df.columns[0]
            analyzed_list = []
            for req in df[col].dropna():
                res = analyze_requirement(str(req), vectorizer, classifier)
                save_to_history(str(req), res['type'], res['ambiguous'], res['ambiguous_words'])
                analyzed_list.append({"requirement": req, "result": res})

            session['uploaded_requirements'] = analyzed_list
            return redirect(url_for('uploaded'))

    users = load_users()
    user = users.get(session.get('user'))
    return render_template('index.html', user=user)

@app.route('/uploaded')
@login_required
def uploaded():
    data = session.get('uploaded_requirements', None)
    if not data or len(data) == 0:
        data = None
    users = load_users()
    user = users.get(session.get('user'))
    return render_template('uploaded.html', requirements=data, user=user)

@app.route('/history')
@login_required
def history():
    filename = 'history.csv'
    if not os.path.exists(filename):
        users = load_users()
        user = users.get(session.get('user'))
        return render_template('history.html', history=[], user=user)
    with open(filename, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        history_data = list(reader)
    users = load_users()
    user = users.get(session.get('user'))
    return render_template('history.html', history=history_data, user=user)


@app.route('/delete_requirement', methods=['POST'])
@login_required
def delete_requirement():
    idx = request.form.get('index')
    if idx is None:
        return redirect(url_for('uploaded'))
    try:
        idx = int(idx)
    except ValueError:
        return redirect(url_for('uploaded'))
    uploaded_reqs = session.get('uploaded_requirements', [])
    if 0 <= idx < len(uploaded_reqs):
        uploaded_reqs.pop(idx)
        session['uploaded_requirements'] = uploaded_reqs
    return redirect(url_for('uploaded'))

@app.route('/clear_all', methods=['POST'])
@login_required
def clear_all_requirements():
    session.pop('uploaded_requirements', None)
    flash("All uploaded requirements have been cleared.", "success")
    return redirect(url_for('uploaded'))

@app.route('/download_uploaded')
@login_required
def download_uploaded():
    data = session.get('uploaded_requirements', [])
    if not data:
        flash("No uploaded requirements to download.", "error")
        return redirect(url_for('uploaded'))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Requirement', 'Type', 'Ambiguous', 'Ambiguous Words'])

    for item in data:
        req = item['requirement']
        result = item['result']
        req_type = result['type']
        ambiguous = 'Yes' if result['ambiguous'] else 'No'
        amb_words = ', '.join([w['word'] for w in result['ambiguous_words']])
        writer.writerow([req, req_type, ambiguous, amb_words])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        download_name='analyzed_requirements.csv',
        as_attachment=True
    )
    
    
    


@app.route('/clear_history', methods=['POST'])
@login_required
def clear_history():
    filename = 'history.csv'
    if os.path.exists(filename):
        os.remove(filename)
        flash("History cleared successfully.", "success")
    else:
        flash("No history file found to clear.", "error")
    return redirect(url_for('history'))

@app.route('/download_history')
@login_required
def download_history():
    filename = 'history.csv'
    if not os.path.exists(filename):
        flash("No history to download.", "error")
        return redirect(url_for('history'))
    return send_file(
        filename,
        mimetype='text/csv',
        download_name='history.csv',
        as_attachment=True
    )


@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/submit_contact', methods=['POST'])
def submit_contact():
    try:
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']

        msg = Message(subject="New Contact Form Submission",
                      recipients=['tasbihaashraf32@gmail.com'],  # 🔁 Where you want to receive the message
                      body=f"Name: {name}\nEmail: {email}\n\nMessage:\n{message}")

        mail.send(msg)

        flash("Your message has been sent successfully!", "success")
        return redirect(url_for('contact'))

    except Exception as e:
        flash(f"An error occurred while sending the message: {str(e)}", "error")
        return redirect(url_for('contact'))
    
@app.route('/help')
def help_page():
    return render_template('help.html')



# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)
