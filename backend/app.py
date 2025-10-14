from flask import Flask, render_template, request, jsonify, send_file
from io import BytesIO
from openai import OpenAI
import os

app = Flask(__name__)


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Friendly and conversational system prompt for the interviewer
FRIENDLY_SYSTEM_PROMPT = (
    "You are a friendly, conversational, and insightful AI interviewer for Tundra Technical. "
    "Dont talk too much. Be concoise and to the point."
    "Your tone should be warm, welcoming, and engaging, helping the candidate feel comfortable while "
    "gently probing for depth and clarity. Use natural language and smooth transitions between questions. "
    "Be sure to listen attentively, acknowledge answers, and guide the conversation like a real human interviewer.Dont talk too much. Be concoise and to the point."
)

interview_sessions = {}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/start_interview", methods=["POST"])
def start_interview():
    data = request.get_json()
    jd = data.get("job_description")
    resume = data.get("resume")

    interview_sessions["context"] = {
        "jd": jd,
        "resume": resume,
        "history": [],
        "questions_asked": 0,
        "max_questions": 10
    }

    prompt = (
        f"{FRIENDLY_SYSTEM_PROMPT}\n\n"
        f"Candidate resume:\n{resume}\n"
        f"Job description:\n{jd}\n"
        f"The interview has a maximum of: {interview_sessions['context']['max_questions']}.Please pace the interview accordingly to cover all areas of interview\n"
        "Begin the interview with a friendly greeting. Dont ask any questions yet."
        "Dont ask too many questions at once, just one at a time."
        "Only after this initial rapport-building, gradually transition to questions that relate to their background or the job description. Be concoise and to the point."
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": prompt}]
    )

    question = response.choices[0].message.content
    interview_sessions["context"]["history"].append({"role": "AI", "content": question})
    interview_sessions["context"]["questions_asked"] += 1

    return jsonify({"question": question})


@app.route("/candidate_answer", methods=["POST"])
def candidate_answer():
    data = request.get_json()
    answer = data.get("answer")

    session = interview_sessions["context"]
    session["history"].append({"role": "Candidate", "content": answer})

    if session["questions_asked"] >= session["max_questions"]:
        return jsonify({"end": True, "message": "That concludes the interview. Thank you for your time."})

    context_text = "\n".join([f"{h['role']}: {h['content']}" for h in session["history"]])

    prompt = (
        f"{FRIENDLY_SYSTEM_PROMPT}\n\n"
        f"Resume:\n{session['resume']}\n"
        f"Job description:\n{session['jd']}\n"
        f"Conversation so far:\n{context_text}\n"
        "Continue the interview in a friendly, conversational manner. "
        "Dont talk too much. Be concoise and to the point."
        "Acknowledge the candidate's previous answer and smoothly transition to the next relevant question. Be concoise and to the point."
         "Dont ask too many questions at once, just one at a time."
        "If enough has been assessed, politely indicate the interview is concluding."
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": prompt}]
    )

    question = response.choices[0].message.content
    session["history"].append({"role": "AI", "content": question})
    session["questions_asked"] += 1

    return jsonify({"question": question, "end": False})


@app.route("/finish_interview", methods=["POST"])
def finish_interview():
    session = interview_sessions["context"]
    conversation = session["history"]
    jd = session["jd"]
    resume = session["resume"]

    prompt = (
        f"{FRIENDLY_SYSTEM_PROMPT}\n\n"
        "You are now wrapping up the interview. Based on the following conversation, "
        "provide a friendly but professional evaluation report for the candidate:\n\n"
        "1. Executive Summary (2–3 sentences)\n"
        "2. Skill Scores (1–10): Technical, Analytical, Communication, Problem-Solving, Interpersonal, JD Alignment\n"
        "3. Qualitative Insights: Emotional Intelligence, Personality & Attitude, Authenticity\n"
        "4. Final Recommendation (Hire/Next Round/Concerns)\n\n"
        f"Resume: {resume}\n"
        f"Job Description: {jd}\n"
        f"Conversation: {conversation}\n"
        "Close the report with a friendly, encouraging note."
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": prompt}]
    )

    report = response.choices[0].message.content
    return jsonify({"report": report})

# ---------- TTS: Text to Speech ----------
@app.route("/tts", methods=["POST"])
def tts():
    data = request.get_json()
    text = data.get("text")
    response = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="cedar",
        input=text
    )
    audio_bytes = BytesIO(response.content)
    audio_bytes.seek(0)
    return send_file(audio_bytes, mimetype="audio/mpeg")

# ---------- STT: Speech to Text ----------
@app.route("/stt", methods=["POST"])
def stt():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file uploaded"}), 400
    file = request.files["audio"]
    audio_bytes = BytesIO(file.read())
    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=("audio.webm", audio_bytes)
    )
    return jsonify({"transcript": transcript.text})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
