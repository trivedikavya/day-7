document.addEventListener("DOMContentLoaded", () => {
  const startScreen = document.getElementById("start-screen");
  const conversationScreen = document.getElementById("conversation-screen");
  const startConvBtn = document.getElementById("start-conv-btn");
  const micToggleBtn = document.getElementById("mic-toggle-btn");
  const statusText = document.getElementById("status-text");
  const agentAudio = document.getElementById("agent-audio");

  const modeCard = document.getElementById("mode-card");
  const dispMode = document.getElementById("disp-mode");
  const dispTopic = document.getElementById("disp-topic");
  const dispFeedback = document.getElementById("disp-feedback");

  let mediaRecorder;
  let audioChunks = [];
  let isRecording = false;

  let currentState = {
    mode: "menu",
    topic_id: null,
    feedback: ""
  };

  // --- START SESSION ---
  startConvBtn.addEventListener("click", async () => {
    startScreen.classList.add("hidden");
    conversationScreen.classList.remove("hidden");
    statusText.textContent = "Class is starting... 🔔";
    
    try {
      const res = await axios.post("http://localhost:5000/start-session");
      if (res.data.audioUrl) {
        playAudio(res.data.audioUrl);
      } else {
        // Fallback for visual only
        statusText.textContent = res.data.text;
        resetMicUI();
      }
    } catch (error) {
      statusText.textContent = "Error connecting.";
      console.error(error);
    }
  });

  // --- MIC TOGGLE ---
  micToggleBtn.addEventListener("click", async () => {
    if (!isRecording) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        mediaRecorder.ondataavailable = event => audioChunks.push(event.data);
        
        mediaRecorder.onstop = async () => {
          statusText.textContent = "Tutor is thinking... 🤔";
          micToggleBtn.innerHTML = "⏳";
          micToggleBtn.disabled = true;
          micToggleBtn.className = "w-24 h-24 rounded-full bg-slate-200 flex items-center justify-center text-4xl text-slate-400";

          const blob = new Blob(audioChunks, { type: 'audio/webm' });
          const formData = new FormData();
          formData.append("file", blob, "recording.webm");
          formData.append("current_state", JSON.stringify(currentState));

          try {
            const res = await axios.post("http://localhost:5000/chat-with-voice", formData);

            if (res.data.updated_state) {
                currentState = res.data.updated_state;
                updateDisplay();
            }

            // --- CRITICAL FIX: Handle Missing Audio ---
            if (res.data.audio_url) {
              playAudio(res.data.audio_url);
            } else {
              console.warn("No audio returned. Displaying text only.");
              statusText.textContent = "Audio failed (See Console). Tap to continue.";
              resetMicUI(); // Forces the button to reset so you aren't stuck!
            }

          } catch (err) {
            console.error(err);
            statusText.textContent = "Connection error.";
            resetMicUI();
          }
        };

        mediaRecorder.start();
        isRecording = true;
        
        statusText.textContent = "Listening...";
        micToggleBtn.innerHTML = "⏹️"; 
        micToggleBtn.className = "w-24 h-24 rounded-full bg-red-500 flex items-center justify-center text-4xl text-white pulse-ring shadow-lg";

      } catch (err) {
        alert("Microphone denied.");
      }

    } else {
      mediaRecorder.stop();
      isRecording = false;
    }
  });

  function updateDisplay() {
    dispMode.textContent = currentState.mode;
    dispTopic.textContent = currentState.topic_id || "None";
    
    modeCard.className = "w-full bg-white rounded-xl p-5 mb-8 border shadow-sm text-left transition-colors duration-500";
    if (currentState.mode === 'learn') modeCard.classList.add('mode-learn');
    else if (currentState.mode === 'quiz') modeCard.classList.add('mode-quiz');
    else if (currentState.mode === 'teach_back') modeCard.classList.add('mode-teach_back');
    else modeCard.classList.add('mode-menu');

    if (currentState.feedback) {
        dispFeedback.classList.remove("hidden");
        dispFeedback.innerHTML = `<strong>Coach Note:</strong> ${currentState.feedback}`;
    } else {
        dispFeedback.classList.add("hidden");
    }
  }

  function playAudio(url) {
    agentAudio.src = url;
    statusText.textContent = "Tutor is speaking... 🗣️";
    agentAudio.play();

    agentAudio.onended = () => {
      resetMicUI();
    };
    
    agentAudio.onerror = () => {
        statusText.textContent = "Audio playback error.";
        resetMicUI();
    };
  }

  function resetMicUI() {
    statusText.textContent = "Tap to Reply";
    micToggleBtn.disabled = false;
    micToggleBtn.innerHTML = "🎙️";
    micToggleBtn.className = "w-24 h-24 rounded-full bg-slate-100 flex items-center justify-center text-4xl shadow-inner transition-all duration-300 text-slate-500 hover:scale-105";
  }
});