from flask import Flask, request, jsonify
import os
import PyPDF2
import re
from werkzeug.utils import secure_filename
import spacy
import nltk
from nltk.corpus import stopwords

nltk.download('punkt')
nltk.download('stopwords')

try:
    nlp = spacy.load("en_core_web_sm")
except:
    os.system("python -m spacy download en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

app = Flask(__name__, static_folder='static', static_url_path='')

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

TECH_KEYWORDS = {
    "languages": ["python", "java", "javascript", "c++", "typescript", "swift", "php", "ruby", "go", "kotlin"],
    "frameworks": ["react", "angular", "django", "flask", "spring", "vue", "node.js", "express", "laravel", "rails"],
    "databases": ["sql", "mysql", "mongodb", "postgresql", "redis", "oracle", "elasticsearch", "firebase", "datomic"],
    "cloud": ["aws", "azure", "gcp", "cloud", "serverless", "docker", "kubernetes", "terraform", "lambda"],
    "methodologies": ["agile", "scrum", "kanban", "ci/cd", "devops", "test-driven", "microservices", "tdd", "bdd"]
}

def analyze_resume(text):
    results = {"score": 0, "strengths": [], "weaknesses": [], "suggestions": [], "keyword_matches": {}}
    lines = text.split('\n')
    word_count = len(re.findall(r'\w+', text))
    sentences = nltk.sent_tokenize(text)
    words = nltk.word_tokenize(text.lower())
    stop_words = set(stopwords.words('english'))
    filtered_words = [w for w in words if w.isalnum() and w not in stop_words]
    page_estimate = int(word_count / 500) + 1

    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    phone_pattern = r'(\d{3}[-\.\s]?\d{3}[-\.\s]?\d{4}|\(\d{3}\)\s*\d{3}[-\.\s]?\d{4}|\d{10})'
    has_email = bool(re.search(email_pattern, text))
    has_phone = bool(re.search(phone_pattern, text))

    education_keywords = ["education", "university", "college", "degree", "bachelor", "master", "phd"]
    has_education = any(keyword in text.lower() for keyword in education_keywords)
    experience_keywords = ["experience", "work", "employment", "job", "career", "position"]
    has_experience = any(keyword in text.lower() for keyword in experience_keywords)
    achievement_indicators = ["increased", "decreased", "improved", "reduced", "achieved", "created", "implemented", "managed", "led", "developed", "built", "%", "percent", "million", "thousand"]
    has_achievements = any(indicator in text.lower() for indicator in achievement_indicators)

    keyword_counts = {}
    for category, keywords in TECH_KEYWORDS.items():
        keyword_counts[category] = []
        for keyword in keywords:
            count = sum(1 for word in filtered_words if keyword == word or keyword in word)
            if count > 0:
                keyword_counts[category].append({"keyword": keyword, "count": count})

    total_keywords = sum(len(category_keywords) for category_keywords in keyword_counts.values())
    base_score = 50
    if has_email: base_score += 5
    if has_phone: base_score += 5
    if has_education: base_score += 10
    if has_experience: base_score += 10
    if has_achievements: base_score += 10
    keyword_score = min(20, total_keywords * 2)
    if page_estimate > 2: base_score -= (page_estimate - 2) * 5
    elif word_count < 300: base_score -= 10
    final_score = max(0, min(100, base_score + keyword_score))

    strengths, weaknesses, suggestions = [], [], []

    if has_email and has_phone:
        strengths.append("Contact information is clearly provided")
    else:
        weaknesses.append("Missing or unclear contact information")
        suggestions.append("Ensure your email and phone number are clearly visible at the top of your resume")

    if has_education:
        strengths.append("Education section is present")
    else:
        weaknesses.append("Education section is missing or not clearly defined")
        suggestions.append("Add a dedicated education section with your degree, institution, and graduation year")

    if has_experience:
        strengths.append("Work experience section is present")
    else:
        weaknesses.append("Work experience section is missing or not clearly defined")
        suggestions.append("Include a detailed work experience section with your job titles, companies, and dates")

    if has_achievements:
        strengths.append("Resume includes measurable achievements")
    else:
        weaknesses.append("Resume lacks measurable achievements and quantifiable results")
        suggestions.append("Quantify your achievements with numbers, percentages, or specific outcomes")

    if total_keywords >= 10:
        strengths.append(f"Good keyword optimization with {total_keywords} industry-relevant terms")
    else:
        weaknesses.append("Limited industry-specific keywords detected")
        flat_keywords = [kw for category in TECH_KEYWORDS.values() for kw in category]
        suggested_keywords = ", ".join(flat_keywords[:5])
        suggestions.append(f"Add more industry keywords such as: {suggested_keywords}")

    if page_estimate > 2:
        weaknesses.append(f"Resume is too long ({page_estimate} pages)")
        suggestions.append("Condense your resume to 1-2 pages by focusing on recent and relevant experience")
    elif word_count < 300:
        weaknesses.append("Resume is too short and may lack sufficient detail")
        suggestions.append("Expand your resume with more details about your skills and experiences")

    results["score"] = final_score
    results["strengths"] = strengths
    results["weaknesses"] = weaknesses
    results["suggestions"] = suggestions
    results["keyword_matches"] = keyword_counts
    results["stats"] = {
        "word_count": word_count,
        "estimated_pages": page_estimate
    }
    return results

@app.route('/analyze-resume', methods=['POST'])
def upload_file():
    if 'resume' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['resume']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            text = ""
            with open(filepath, 'rb') as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                for page_num in range(len(pdf_reader.pages)):
                    text += pdf_reader.pages[page_num].extract_text()

            results = analyze_resume(text)
            os.remove(filepath)
            return jsonify(results)
        except Exception as e:
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'File type not allowed'}), 400

@app.route('/')
def serve_index():
    return app.send_static_file('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
