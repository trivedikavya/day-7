document.addEventListener("DOMContentLoaded", () => {
  const startScreen = document.getElementById("start-screen");
  const conversationScreen = document.getElementById("conversation-screen");
  const startConvBtn = document.getElementById("start-conv-btn");
  const micToggleBtn = document.getElementById("mic-toggle-btn");
  const statusText = document.getElementById("status-text");
  const agentAudio = document.getElementById("agent-audio");

  let mediaRecorder;
  let audioChunks = [];
  let isRecording = false;

  // --- 1. START CONVERSATION FLOW ---
  startConvBtn.addEventListener("click", async () => {
    // Switch UI
    startScreen.classList.add("hidden");
    conversationScreen.classList.remove("hidden");
    statusText.textContent = "AQUA is connecting...";

    try {
      // Request Greeting Audio
      const res = await axios.post("http://localhost:5000/server", {
        text: "Hello! I am Aqua. We can start our conversation now."
      });

      if (res.data.audioUrl) {
        playAudio(res.data.audioUrl);
      }
    } catch (error) {
      statusText.textContent = "Error starting conversation.";
      console.error(error);
    }
  });

  // --- 2. MIC TOGGLE LOGIC ---
  micToggleBtn.addEventListener("click", async () => {
    if (!isRecording) {
      // START RECORDING
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = event => audioChunks.push(event.data);
        
        mediaRecorder.onstop = async () => {
          // USER STOPPED -> SEND TO SERVER
          statusText.textContent = "AQUA is thinking... 🧠";
          micToggleBtn.classList.remove("bg-red-500", "text-white", "pulse-ring");
          micToggleBtn.classList.add("bg-gray-200", "text-gray-400"); // Disable visual
          micToggleBtn.disabled = true; // Prevent clicking while loading

          const blob = new Blob(audioChunks, { type: 'audio/webm' });
          const formData = new FormData();
          formData.append("file", blob, "recording.webm");

          try {
            // SEND TO BACKEND
            const res = await axios.post("http://localhost:5000/chat-with-voice", formData, {
              headers: { "Content-Type": "multipart/form-data" }
            });

            // PLAY RESPONSE
            if (res.data.audio_url) {
              playAudio(res.data.audio_url);
            } else {
              statusText.textContent = "I didn't hear that.";
              resetMicUI();
            }

          } catch (err) {
            console.error(err);
            statusText.textContent = "Error connecting to Aqua.";
            resetMicUI();
          }
        };

        mediaRecorder.start();
        isRecording = true;
        
        // UI UPDATES (Mic ON)
        statusText.textContent = "Listening... 👂";
        micToggleBtn.innerHTML = "⏹️"; // Stop Icon
        micToggleBtn.classList.remove("bg-gray-200");
        micToggleBtn.classList.add("bg-red-500", "text-white", "pulse-ring");

      } catch (err) {
        alert("Microphone permission denied.");
      }

    } else {
      // STOP RECORDING
      mediaRecorder.stop(); // This triggers mediaRecorder.onstop above
      isRecording = false;
      micToggleBtn.innerHTML = "🎙️";
    }
  });

  // Helper: Play Audio and update UI
  function playAudio(url) {
    agentAudio.src = url;
    statusText.textContent = "AQUA is speaking... 🗣️";
    agentAudio.play();

    // When audio finishes, reset UI so user can talk again
    agentAudio.onended = () => {
      resetMicUI();
    };
  }

  // Helper: Reset Mic Button to "Ready" state
  function resetMicUI() {
    statusText.textContent = "Tap Mic to Reply";
    micToggleBtn.disabled = false;
    micToggleBtn.classList.remove("bg-gray-400");
    micToggleBtn.classList.add("bg-gray-200", "text-gray-800");
    micToggleBtn.innerHTML = "🎙️";
  }
});