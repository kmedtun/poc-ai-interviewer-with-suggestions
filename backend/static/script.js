const startBtn = document.getElementById("start-btn");
const inputSection = document.getElementById("input-section");
const chatSection = document.getElementById("chat-section");
const chatWindow = document.getElementById("chat-window");
const micIndicator = document.querySelector(".mic-indicator");
const reportSection = document.getElementById("report-section");
const reportContent = document.getElementById("report-content");

let isInterviewRunning = false;
let mediaRecorder;
let audioChunks = [];

function addMessage(role, text) {
  const msg = document.createElement("div");
  msg.classList.add("message", role.toLowerCase());
  const bubble = document.createElement("div");
  bubble.classList.add("bubble");
  bubble.textContent = text;
  msg.appendChild(bubble);
  chatWindow.appendChild(msg);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

async function playQuestion(text) {
  try {
    const res = await fetch("/tts", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ text })
    });
    if (!res.ok) {
      throw new Error(`TTS request failed with status ${res.status}`);
    }
    const audioBlob = await res.blob();
    const audioUrl = URL.createObjectURL(audioBlob);
    const audio = new Audio(audioUrl);
    audio.play();
  } catch (error) {
    console.error("Error in playQuestion:", error);
    addMessage("AI", "Sorry, I am unable to play the question audio at the moment.");
  }
}

startBtn.addEventListener("click", async () => {
  const jd = document.getElementById("job-description").value;
  const resume = document.getElementById("resume").value;
  inputSection.classList.add("hidden");
  chatSection.classList.remove("hidden");

  const res = await fetch("/start_interview", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ job_description: jd, resume: resume })
  });

  const data = await res.json();
  addMessage("AI", data.question);
  await playQuestion(data.question);
  isInterviewRunning = true;
});

async function startRecording() {
  if (!isInterviewRunning) return;
  micIndicator.classList.add("active");
  micIndicator.classList.remove("hidden");
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];

    mediaRecorder.addEventListener("dataavailable", event => {
      audioChunks.push(event.data);
    });

    mediaRecorder.addEventListener("stop", async () => {
      micIndicator.classList.remove("active");
      micIndicator.classList.add("hidden");
      const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
      audioChunks = [];
      const formData = new FormData();
      formData.append("audio", audioBlob);

      try {
        const sttRes = await fetch("/stt", {
          method: "POST",
          body: formData
        });
        if (!sttRes.ok) {
          throw new Error(`STT request failed with status ${sttRes.status}`);
        }
        const sttData = await sttRes.json();
        const transcript = sttData.transcript;

        addMessage("Candidate", transcript);

        const res = await fetch("/candidate_answer", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({ answer: transcript })
        });
        const data = await res.json();
        if (data.end) {
          addMessage("AI", data.message);
          const reportRes = await fetch("/finish_interview", { method: "POST" });
          const reportData = await reportRes.json();
          chatSection.classList.add("hidden");
          reportSection.classList.remove("hidden");
          reportContent.textContent = reportData.report;
          isInterviewRunning = false;
        } else {
          addMessage("AI", data.question);
          await playQuestion(data.question);
        }
      } catch (error) {
        console.error("Error during STT or processing candidate answer:", error);
        addMessage("AI", "Sorry, there was an error processing your answer. Please try again.");
      }
    });

    mediaRecorder.start();
  } catch (error) {
    micIndicator.classList.remove("active");
    micIndicator.classList.add("hidden");
    console.error("Error accessing microphone:", error);
    addMessage("AI", "Unable to access the microphone. Please check your peryemissions and try again.");
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
    audioChunks = [];
  }
}
