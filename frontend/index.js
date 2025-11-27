document.addEventListener("DOMContentLoaded", () => {
  const startScreen = document.getElementById("start-screen");
  const conversationScreen = document.getElementById("conversation-screen");
  const startConvBtn = document.getElementById("start-conv-btn");
  const micToggleBtn = document.getElementById("mic-toggle-btn");
  const statusText = document.getElementById("status-text");
  const agentAudio = document.getElementById("agent-audio");

  // Status Badges
  const dispVerif = document.getElementById("disp-verification");
  const dispCase = document.getElementById("disp-case-status");
  const connDot = document.getElementById("connection-dot");

  let mediaRecorder;
  let audioChunks = [];
  let isRecording = false;

  let currentState = {
    verification_stage: "unverified",
    case_status: "pending"
  };

  // --- START SECURE CALL ---
  startConvBtn.addEventListener("click", async () => {
    startScreen.classList.add("hidden");
    conversationScreen.classList.remove("hidden");
    statusText.textContent = "Establishing Secure Line... 🔒";
    
    try {
      const res = await axios.post("http://localhost:5000/start-session");
      if (res.data.audioUrl) {
        playAudio(res.data.audioUrl);
      } else {
        statusText.textContent = res.data.text;
        resetMicUI();
      }
    } catch (error) {
      statusText.textContent = "Connection Failed.";
      console.error(error);
    }
  });

  // --- MIC LOGIC ---
  micToggleBtn.addEventListener("click", async () => {
    if (!isRecording) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        mediaRecorder.ondataavailable = event => audioChunks.push(event.data);
        
        mediaRecorder.onstop = async () => {
          statusText.textContent = "Verifying... 🔐";
          micToggleBtn.innerHTML = "⏳";
          micToggleBtn.disabled = true;
          micToggleBtn.className = "w-20 h-20 rounded-full bg-gray-200 flex items-center justify-center text-3xl text-gray-400";

          const blob = new Blob(audioChunks, { type: 'audio/webm' });
          const formData = new FormData();
          formData.append("file", blob, "recording.webm");
          formData.append("current_state", JSON.stringify(currentState));

          try {
            const res = await axios.post("http://localhost:5000/chat-with-voice", formData);

            // Update State
            if (res.data.updated_state) {
                currentState = res.data.updated_state;
                updateSecurityUI();
            }

            if (res.data.audio_url) {
              playAudio(res.data.audio_url);
            } else {
              statusText.textContent = "Agent response error.";
              resetMicUI();
            }

          } catch (err) {
            console.error(err);
            statusText.textContent = "Secure connection dropped.";
            resetMicUI();
          }
        };

        mediaRecorder.start();
        isRecording = true;
        
        statusText.textContent = "Listening...";
        micToggleBtn.innerHTML = "⏹️"; 
        micToggleBtn.className = "w-20 h-20 rounded-full bg-red-600 flex items-center justify-center text-3xl text-white shadow-lg pulse-alert";

      } catch (err) {
        alert("Microphone denied.");
      }

    } else {
      mediaRecorder.stop();
      isRecording = false;
    }
  });

  function updateSecurityUI() {
    // 1. Verification Badge
    if (currentState.verification_stage === "verified") {
        dispVerif.textContent = "VERIFIED ✅";
        dispVerif.className = "font-bold text-green-600";
    } else {
        dispVerif.textContent = "PENDING ⚠️";
        dispVerif.className = "font-bold text-yellow-600";
    }

    // 2. Case Status Badge
    if (currentState.case_status === "safe") {
        dispCase.textContent = "CLEARED ✅";
        dispCase.className = "font-bold text-green-600";
        connDot.className = "w-3 h-3 bg-green-500 rounded-full";
    } else if (currentState.case_status === "fraudulent") {
        dispCase.textContent = "BLOCKED ⛔";
        dispCase.className = "font-bold text-red-600";
        connDot.className = "w-3 h-3 bg-red-500 rounded-full";
    }
  }

  function playAudio(url) {
    agentAudio.src = url;
    statusText.textContent = "Agent is speaking... 🗣️";
    agentAudio.play();

    agentAudio.onended = () => {
      if (currentState.case_status !== "pending") {
        statusText.textContent = "Case Closed. Connection Ended.";
        micToggleBtn.innerHTML = "🔒";
        micToggleBtn.disabled = true;
      } else {
        resetMicUI();
      }
    };
  }

  function resetMicUI() {
    statusText.textContent = "Tap to Verify";
    micToggleBtn.disabled = false;
    micToggleBtn.innerHTML = "🎙️";
    micToggleBtn.className = "w-20 h-20 rounded-full bg-blue-50 border-2 border-blue-100 flex items-center justify-center text-3xl text-blue-900 transition-all hover:bg-blue-100";
  }
});