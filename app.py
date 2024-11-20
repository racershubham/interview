import openai
from flask import Flask, render_template, request, jsonify, session
from pymongo import MongoClient
from flask_cors import CORS  # Import CORS

import random
import string

app = Flask(__name__)

# Enable CORS for all origins (all websites)
CORS(app)

# Set secret key for session management
app.secret_key = "supersecretkey"

# MongoDB connection
client = MongoClient('mongodb://localhost:27017/')
db = client['interview_db']

# OpenAI API key
openai.api_key = "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"

@app.route('/')
def index():
    return render_template('index.html')

def generate_id_password():
    interview_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    return interview_id, password

def generate_questions(job_description, num_questions=15):
    questions = []
    question_prompt = f"Generate {num_questions} interview questions for a candidate applying for a position: {job_description}"
    
    # Call OpenAI to generate a list of questions based on the job description
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that generates interview questions based on job descriptions."},
            {"role": "user", "content": question_prompt}
        ],
        max_tokens=500  # Allow enough tokens to get 15 questions
    )
    
    # Extract questions from the response
    message = response['choices'][0]['message']['content']
    questions = message.split('\n')
    
    # Filter out any empty strings or malformed responses
    questions = [q.strip() for q in questions if q.strip()]
    return questions[:num_questions]  # Ensure we only get 15 questions

@app.route('/create_interview', methods=['POST'])
def create_interview():
    data = request.get_json()
    job_description = data.get("job_description")
    
    # Generate interview ID and password
    interview_id, password = generate_id_password()
    
    # Generate 15 interview questions based on the job description
    questions = generate_questions(job_description)
    
    # Insert interview data into MongoDB
    db.interviews.insert_one({
        "interview_id": interview_id,
        "password": password,
        "job_description": job_description,
        "questions": questions,  # Save all 15 questions
        "responses": [],
        "question_count": 0,
        "interview_status": "in-progress"  # Initially the interview is in progress
    })

    # Return the interview ID, password, and confirmation message
    return jsonify({
        "interview_id": interview_id,
        "password": password,
        "questions": questions
    }), 201

@app.route('/start_interview_page', methods=['GET'])
def start_interview_page():
    return render_template('start_interview.html')

@app.route('/start_interview', methods=['POST'])
def start_interview():
    data = request.get_json()
    interview_id = data.get("interview_id")
    password = data.get("password")
    
    # Fetch the interview from the database using the provided ID and password
    interview = db.interviews.find_one({"interview_id": interview_id, "password": password})
    if not interview:
        return jsonify({"error": "Invalid ID or Password"}), 403
    
    # Store the interview ID in the session
    session['interview_id'] = interview_id
    return jsonify({"message": "Interview started", "questions": interview["questions"]}), 200


@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    if 'interview_id' not in session:
        return jsonify({"error": "Interview not started"}), 403
    
    data = request.get_json()
    question_index = data.get("question_index")
    answer = data.get("answer")
    interview_id = session['interview_id']
    
    interview = db.interviews.find_one({"interview_id": interview_id})

    # Check if the interview exists
    if not interview:
        return jsonify({"error": "Interview not found"}), 404

    # Save the answer to the database
    db.interviews.update_one(
        {"interview_id": interview_id},
        {"$push": {"responses": {"question": interview["questions"][question_index], "answer": answer}}}
    )

    # Update the question count
    db.interviews.update_one(
        {"interview_id": interview_id},
        {"$inc": {"question_count": 1}}
    )

    # If all questions are answered, mark the interview as complete
    if interview["question_count"] + 1 >= len(interview["questions"]):
        db.interviews.update_one(
            {"interview_id": interview_id},
            {"$set": {"interview_status": "completed"}}
        )

    return jsonify({"message": "Answer recorded"}), 200


if __name__ == '__main__':
    app.run(debug=True)
