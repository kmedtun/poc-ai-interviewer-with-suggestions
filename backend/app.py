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
        "You are now acting as both an interviewer and a mentor helping the candidate improve. "
        "For each candidate answer, first provide a brief, encouraging acknowledgement, "
        "then give actionable feedback (how they could have structured or improved the answer), "
        "and finally, ask the next relevant interview question. "
        "Keep your tone friendly, supportive, and concise. "
        "Output format:\n"
        "Feedback: <your feedback here>\n"
        "Next question: <your next question here>\n\n"
        f"Resume:\n{session['resume']}\n"
        f"Job description:\n{session['jd']}\n"
        f"Conversation so far:\n{context_text}\n"
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": prompt}]
    )

    full_response = response.choices[0].message.content
    feedback, next_question = "", full_response
    if "Feedback:" in full_response and "Next question:" in full_response:
        parts = full_response.split("Next question:")
        feedback = parts[0].replace("Feedback:", "").strip()
        next_question = parts[1].strip()

    session["history"].append({"role": "AI", "content": feedback})
    session["history"].append({"role": "AI", "content": next_question})
    session["questions_asked"] += 1

    return jsonify({"feedback": feedback, "question": next_question, "end": False})


@app.route("/finish_interview", methods=["POST"])
def finish_interview():
    session = interview_sessions["context"]
    conversation = session["history"]
    jd = session["jd"]
    resume = session["resume"]

    prompt = (
        f"{FRIENDLY_SYSTEM_PROMPT}\n\n"
        "You are now wrapping up the interview as both an interviewer and a mentor. "
        "Based on the following conversation, create a **comprehensive, structured evaluation report** for the candidate.\n\n"
        "The report should include:\n\n"
        "1. **Executive Summary** – A 2–3 sentence overview of how the candidate performed overall.\n\n"
        "2. **Detailed Skill Evaluation (with 1–10 scores)** – Use a bullet list with clear reasoning for each:\n"
        "   - Technical Knowledge\n"
        "   - Analytical Thinking\n"
        "   - Communication Skills\n"
        "   - Problem-Solving Skills\n"
        "   - Interpersonal & Collaboration\n"
        "   - Alignment with Job Description\n"
        "   - Confidence & Clarity of Thought\n\n"
        "3. **Interview Performance Review** – Summarize strengths and weaknesses observed in their answers. "
        "Highlight what the candidate did well, and what aspects of their approach could be refined.\n\n"
        "4. **Skill Enhancement Recommendations** – Provide actionable feedback on how the candidate can improve their interview performance. "
        "For each major skill area (technical, communication, analytical, etc.), list practical steps and examples of how to improve. "
        "Include advice on tone, pacing, clarity, and storytelling techniques during interviews.\n\n"
        "5. **Sample Improved Answers (Optional)** – For 1–2 of the weaker answers, give a short example of how a more effective response could have been structured.\n\n"
        "6. **Final Recommendation** – (Hire/Next Round/Needs Improvement) with a short justification.\n\n"
        "Ensure the tone remains friendly, constructive, and motivating throughout. "
        "The goal is to help the candidate become better, not just judge them.\n\n"
        f"Resume: {resume}\n"
        f"Job Description: {jd}\n"
        f"Conversation: {conversation}\n"
        "End the report with a short, positive note of encouragement."
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
