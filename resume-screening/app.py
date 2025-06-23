# app.py - Flask application for HR resume screening
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import uuid
from PyPDF2 import PdfMerger
import openai
import pandas as pd
import numpy as np
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Debug info for environment variables
api_key = os.environ.get('OPENAI_API_KEY')
print(f"API key loaded from .env: {'Yes' if api_key else 'No'}")
if api_key:
    print(f"First few characters of API key: {api_key[:10]}...")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_key')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MERGED_FOLDER'] = 'merged'
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}

# Create folders if they don't exist
for folder in [app.config['UPLOAD_FOLDER'], app.config['MERGED_FOLDER']]:
    os.makedirs(folder, exist_ok=True)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Mock database for users (replace with a real database in production)
users = {
    'hr@example.com': {
        'password': generate_password_hash('password123'),
        'role': 'hr'
    }
}

# User model for Flask-Login
class User(UserMixin):
    def __init__(self, id, role):
        self.id = id
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    if user_id in users:
        return User(user_id, users[user_id]['role'])
    return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def merge_pdfs(pdf_files, output_filename):
    merger = PdfMerger()
    
    for pdf in pdf_files:
        merger.append(pdf)
    
    output_path = os.path.join(app.config['MERGED_FOLDER'], output_filename)
    merger.write(output_path)
    merger.close()
    return output_path

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file with improved error handling"""
    try:
        import PyPDF2
        
        text = ""
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        
        if not text.strip():
            print(f"Warning: No text extracted from {pdf_path}")
            return "No text could be extracted from this PDF."
        
        return text
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {str(e)}")
        return f"Error extracting text: {str(e)}"

def analyze_resumes(resumes_text, job_description):
    """
    Analyze resumes against a job description to find the best matches
    Using OpenAI API as an example (can be replaced with local models like Ollama)
    """
    try:
        api_key = os.environ.get('OPENAI_API_KEY')
        print(f"API key in analyze_resumes: {'Yes' if api_key else 'No'}")
        
        if not api_key:
            print("Error: OpenAI API key not found")
            return [{"resume_idx": i, "score": 0, "strengths": ["API error: Missing API key"], 
                     "gaps": ["Contact administrator"]} for i in range(len(resumes_text))]
        
        openai.api_key = api_key
        
        # Prepare results storage
        results = []
        
        # For each resume, compare with job description
        for idx, resume_text in enumerate(resumes_text):
            try:
                print(f"Processing resume {idx+1}/{len(resumes_text)}")
                print(f"Resume text length: {len(resume_text)}")
                
                # Ensure resume text isn't empty
                if not resume_text or len(resume_text.strip()) < 50:
                    print(f"Warning: Resume {idx} has insufficient text")
                    results.append({
                        "resume_idx": idx,
                        "score": 0,
                        "strengths": ["Error: Could not extract sufficient text from PDF"],
                        "gaps": ["Please check PDF quality and format"]
                    })
                    continue
                
                # Create a prompt for the language model
                prompt = f"""
                You are an HR assistant analyzing resumes for job fit.
                
                JOB DESCRIPTION:
                {job_description}
                
                RESUME:
                {resume_text[:4000]}  # Truncate if too long
                
                Based on the job description and resume, provide:
                1. A matching score from 0-100
                2. Top 3 reasons this candidate might be a good fit
                3. Top 3 potential gaps in experience or skills
                Format your response as JSON with keys: "score", "strengths", "gaps"
                """
                
                # Try using the newer OpenAI client if available
                try:
                    # Try with newer client version first
                    from openai import OpenAI
                    client = OpenAI(api_key=api_key)
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "You analyze resumes and provide structured feedback as valid JSON."},
                            {"role": "user", "content": prompt}
                        ],
                        response_format={"type": "json_object"}
                    )
                    analysis = response.choices[0].message.content
                except ImportError:
                    # Fall back to older client version
                    print("Using older OpenAI client")
                    response = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "You analyze resumes and provide structured feedback as valid JSON."},
                            {"role": "user", "content": prompt}
                        ],
                        response_format={"type": "json_object"}
                    )
                    analysis = response.choices[0].message.content
                
                print(f"Got response for resume {idx}")
                
                # For a real app, use proper JSON parsing with error handling
                analysis_json = json.loads(analysis)
                
                # Store the result with resume index
                results.append({
                    "resume_idx": idx,
                    "score": analysis_json.get("score", 0),
                    "strengths": analysis_json.get("strengths", []),
                    "gaps": analysis_json.get("gaps", [])
                })
                
            except json.JSONDecodeError as e:
                print(f"JSON parsing error for resume {idx}: {str(e)}")
                print(f"Raw response: {analysis if 'analysis' in locals() else 'No response'}")
                results.append({
                    "resume_idx": idx,
                    "score": 0,
                    "strengths": ["Error in parsing analysis"],
                    "gaps": ["Technical error - contact administrator"]
                })
            except Exception as e:
                # Handle errors - in production, log these properly
                print(f"Error analyzing resume {idx}: {str(e)}")
                results.append({
                    "resume_idx": idx,
                    "score": 0,
                    "strengths": ["Error in analysis"],
                    "gaps": ["Technical error - contact administrator"]
                })
        
        # Sort by score descending and return top 10
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:10]
    
    except Exception as e:
        print(f"Critical error in analyze_resumes: {str(e)}")
        return [{"resume_idx": i, "score": 0, "strengths": ["System error"], 
                 "gaps": ["Contact administrator"]} for i in range(len(resumes_text))]

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if email in users and check_password_hash(users[email]['password'], password):
            user = User(email, users[email]['role'])
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        # Check if job description is provided
        if 'job_description' not in request.form or not request.form['job_description'].strip():
            flash('Job description is required', 'danger')
            return redirect(request.url)
        
        # Check if the post request has the file part
        if 'resumes' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        
        files = request.files.getlist('resumes')
        
        # If user does not select file, browser also
        # submit an empty part without filename
        if not files or files[0].filename == '':
            flash('No selected files', 'danger')
            return redirect(request.url)
        
        # Check if at least one file is valid
        valid_files = [f for f in files if f and allowed_file(f.filename)]
        if not valid_files:
            flash('Please upload PDF files only', 'danger')
            return redirect(request.url)
        
        # Create a folder for this upload session
        session_id = str(uuid.uuid4())
        session_folder = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
        os.makedirs(session_folder, exist_ok=True)
        
        # Save all files
        pdf_paths = []
        for file in valid_files:
            filename = secure_filename(file.filename)
            file_path = os.path.join(session_folder, filename)
            file.save(file_path)
            pdf_paths.append(file_path)
        
        # Merge the PDFs
        merged_filename = f"merged_{session_id}.pdf"
        merged_path = merge_pdfs(pdf_paths, merged_filename)
        
        # Store the job description
        job_description = request.form['job_description']
        
        # Extract text from each resume
        resumes_text = [extract_text_from_pdf(pdf_path) for pdf_path in pdf_paths]
        
        # Analyze resumes against job description
        results = analyze_resumes(resumes_text, job_description)
        
        # Store file paths and results in session for the results page
        session['pdf_paths'] = pdf_paths
        session['merged_path'] = merged_path
        session['results'] = results
        session['original_filenames'] = [secure_filename(f.filename) for f in valid_files]
        
        return redirect(url_for('results'))
    
    return render_template('upload.html')

@app.route('/results')
@login_required
def results():
    if 'results' not in session:
        flash('No results to display', 'warning')
        return redirect(url_for('upload'))
    
    return render_template(
        'results.html',
        results=session['results'],
        filenames=session['original_filenames'],
        merged_path=session['merged_path']
    )

@app.route('/download/<path:filename>')
@login_required
def download_file(filename):
    return send_file(filename, as_attachment=True)

@app.route('/debug_api', methods=['GET'])
@login_required
def debug_api():
    try:
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            return "API key not found in environment"
        
        # Try with newer client version first
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Say hello"}],
                max_tokens=10
            )
            return f"API test successful: {response.choices[0].message.content}"
        except ImportError:
            # Fall back to older client version
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Say hello"}],
                max_tokens=10
            )
            return f"API test successful: {response.choices[0].message.content}"
    except Exception as e:
        return f"API test failed: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True)