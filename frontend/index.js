document.addEventListener("DOMContentLoaded", () => {
  const startScreen = document.getElementById("start-screen");
  const conversationScreen = document.getElementById("conversation-screen");
  const startConvBtn = document.getElementById("start-conv-btn");
  const micToggleBtn = document.getElementById("mic-toggle-btn");
  const statusText = document.getElementById("status-text");
  const agentAudio = document.getElementById("agent-audio");

  // Cart UI
  const cartList = document.getElementById("cart-list");
  const cartTotal = document.getElementById("cart-total");
  const checkoutBtn = document.getElementById("checkout-btn");

  let mediaRecorder;
  let audioChunks = [];
  let isRecording = false;

  let currentState = {
    cart: [],
    total_price: 0,
    is_complete: false
  };

  // --- START ---
  startConvBtn.addEventListener("click", async () => {
    startScreen.classList.add("hidden");
    conversationScreen.classList.remove("hidden");
    statusText.textContent = "Opening Store... 🏪";
    
    try {
      const res = await axios.post("http://localhost:5000/start-session");
      if (res.data.audioUrl) {
        playAudio(res.data.audioUrl);
      } else {
        statusText.textContent = res.data.text;
        resetMicUI();
      }
    } catch (error) {
      statusText.textContent = "Failed to connect.";
      console.error(error);
    }
  });

  // --- MIC ---
  micToggleBtn.addEventListener("click", async () => {
    if (!isRecording) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        mediaRecorder.ondataavailable = event => audioChunks.push(event.data);
        
        mediaRecorder.onstop = async () => {
          statusText.textContent = "Updating Cart... 🛒";
          micToggleBtn.innerHTML = "⏳";
          micToggleBtn.disabled = true;
          micToggleBtn.className = "w-24 h-24 rounded-full bg-gray-200 flex items-center justify-center text-3xl text-gray-400";

          const blob = new Blob(audioChunks, { type: 'audio/webm' });
          const formData = new FormData();
          formData.append("file", blob, "recording.webm");
          formData.append("current_state", JSON.stringify(currentState));

          try {
            const res = await axios.post("http://localhost:5000/chat-with-voice", formData);

            // Update State & UI
            if (res.data.updated_state) {
                currentState = res.data.updated_state;
                renderCart(currentState.cart);
                cartTotal.textContent = `₹${currentState.total_price}`;
            }

            if (res.data.audio_url) {
              playAudio(res.data.audio_url);
            } else {
              statusText.textContent = "No audio returned.";
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
        micToggleBtn.className = "w-24 h-24 rounded-full bg-green-500 flex items-center justify-center text-3xl text-white pulse-btn shadow-lg";

      } catch (err) {
        alert("Microphone denied.");
      }

    } else {
      mediaRecorder.stop();
      isRecording = false;
    }
  });

  // Render Cart Items HTML
  function renderCart(items) {
    if (!items || items.length === 0) {
        cartList.innerHTML = '<div class="text-center text-gray-400 mt-20 italic">Cart is empty</div>';
        return;
    }

    cartList.innerHTML = items.map(item => `
        <div class="cart-item py-3 flex justify-between items-center">
            <div class="flex items-center gap-3">
                <div class="w-8 h-8 bg-gray-100 rounded flex items-center justify-center text-xs font-bold text-gray-500">
                    x${item.qty}
                </div>
                <div>
                    <p class="font-bold text-gray-800 text-sm">${item.name}</p>
                    <p class="text-xs text-gray-500">₹${item.price} / unit</p>
                </div>
            </div>
            <div class="font-bold text-gray-800">₹${item.price * item.qty}</div>
        </div>
    `).join("");
  }

  function playAudio(url) {
    agentAudio.src = url;
    statusText.textContent = "Agent is speaking... 🗣️";
    agentAudio.play();

    agentAudio.onended = () => {
      if (currentState.is_complete) {
        statusText.textContent = "Order Placed! ✅";
        micToggleBtn.innerHTML = "🎉";
        micToggleBtn.disabled = true;
        checkoutBtn.className = "w-full bg-green-600 text-white font-bold py-3 rounded-xl shadow-lg";
        checkoutBtn.textContent = "Order Placed Successfully";
      } else {
        resetMicUI();
      }
    };
  }

  function resetMicUI() {
    statusText.textContent = "Tap to Add Items";
    micToggleBtn.disabled = false;
    micToggleBtn.innerHTML = "🎙️";
    micToggleBtn.className = "w-24 h-24 rounded-full bg-yellow-100 flex items-center justify-center text-4xl text-yellow-600 transition-all hover:bg-yellow-200 hover:scale-105";
  }
});