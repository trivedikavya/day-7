document.addEventListener("DOMContentLoaded", () => {
  const startScreen = document.getElementById("start-screen");
  const conversationScreen = document.getElementById("conversation-screen");
  const startConvBtn = document.getElementById("start-conv-btn");
  const micToggleBtn = document.getElementById("mic-toggle-btn");
  const statusText = document.getElementById("status-text");
  const agentAudio = document.getElementById("agent-audio");

  // CRM Fields
  const crmName = document.getElementById("crm-name");
  const crmCompany = document.getElementById("crm-company");
  const crmRole = document.getElementById("crm-role");
  const crmTeam = document.getElementById("crm-team");
  const crmTimeline = document.getElementById("crm-timeline");
  const crmUseCase = document.getElementById("crm-usecase");

  let mediaRecorder;
  let audioChunks = [];
  let isRecording = false;

  let currentState = {
    lead_info: {},
    is_complete: false
  };

  // --- START CALL ---
  startConvBtn.addEventListener("click", async () => {
    startScreen.classList.add("hidden");
    conversationScreen.classList.remove("hidden");
    statusText.textContent = "Dialing Agent... 📞";
    
    try {
      const res = await axios.post("http://localhost:5000/start-session");
      if (res.data.audioUrl) {
        playAudio(res.data.audioUrl);
      } else {
        statusText.textContent = res.data.text;
        resetMicUI();
      }
    } catch (error) {
      statusText.textContent = "Call Failed.";
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
          statusText.textContent = "Agent is writing... 📝";
          micToggleBtn.innerHTML = "⏳";
          micToggleBtn.disabled = true;
          micToggleBtn.className = "w-20 h-20 rounded-full bg-gray-200 flex items-center justify-center text-3xl text-gray-400";

          const blob = new Blob(audioChunks, { type: 'audio/webm' });
          const formData = new FormData();
          formData.append("file", blob, "recording.webm");
          formData.append("current_state", JSON.stringify(currentState));

          try {
            const res = await axios.post("http://localhost:5000/chat-with-voice", formData);

            // Update State & CRM UI
            if (res.data.updated_state) {
                currentState = res.data.updated_state;
                updateCRM(currentState.lead_info);
            }

            if (res.data.audio_url) {
              playAudio(res.data.audio_url);
            } else {
              statusText.textContent = "No audio. Check console.";
              resetMicUI();
            }

          } catch (err) {
            console.error(err);
            statusText.textContent = "Connection drop.";
            resetMicUI();
          }
        };

        mediaRecorder.start();
        isRecording = true;
        statusText.textContent = "Listening...";
        micToggleBtn.innerHTML = "⏹️"; 
        micToggleBtn.className = "w-20 h-20 rounded-full bg-red-600 flex items-center justify-center text-3xl text-white pulse-ring shadow-lg";

      } catch (err) {
        alert("Microphone denied.");
      }

    } else {
      mediaRecorder.stop();
      isRecording = false;
    }
  });

  function updateCRM(info) {
    if (!info) return;
    crmName.textContent = info.name || "-";
    crmCompany.textContent = info.company_name || "-";
    crmRole.textContent = info.role || "-";
    crmTeam.textContent = info.team_size || "-";
    crmTimeline.textContent = info.timeline || "-";
    crmUseCase.textContent = info.use_case || "-";
  }

  function playAudio(url) {
    agentAudio.src = url;
    statusText.textContent = "Agent is speaking... 🗣️";
    agentAudio.play();

    agentAudio.onended = () => {
      if (currentState.is_complete) {
        statusText.textContent = "Call Ended. Lead Saved. ✅";
        micToggleBtn.innerHTML = "📞";
        micToggleBtn.disabled = true;
      } else {
        resetMicUI();
      }
    };
  }

  function resetMicUI() {
    statusText.textContent = "Tap to Reply";
    micToggleBtn.disabled = false;
    micToggleBtn.innerHTML = "🎙️";
    micToggleBtn.className = "w-20 h-20 rounded-full bg-gray-100 flex items-center justify-center text-3xl text-gray-500 transition-all hover:bg-gray-200";
  }
});