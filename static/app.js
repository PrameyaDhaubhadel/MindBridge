const chatForm = document.getElementById("chatForm");
const chatWindow = document.getElementById("chatWindow");
const statusText = document.getElementById("statusText");
const liveTranscript = document.getElementById("liveTranscript");
const voiceSelect = document.getElementById("voiceSelect");
const holdToTalkButton = document.getElementById("holdToTalkButton");
const logoutButton = document.getElementById("logoutButton");
const userBadge = document.getElementById("userBadge");
const chatCard = document.getElementById("chatCard");
const messageTemplate = document.getElementById("messageTemplate");
const authCard = document.getElementById("authCard");
const authStatus = document.getElementById("authStatus");
const loginForm = document.getElementById("loginForm");
const registerForm = document.getElementById("registerForm");
const loginUsername = document.getElementById("loginUsername");
const loginPassword = document.getElementById("loginPassword");
const registerDisplayName = document.getElementById("registerDisplayName");
const registerUsername = document.getElementById("registerUsername");
const registerPassword = document.getElementById("registerPassword");

const history = [];
const SESSION_USER_KEY = "mindbridge_session_user";
const TTS_PROFILE_KEY = "mindbridge_tts_profile";

let currentUser = null;
let speechRecognition = null;
let isListening = false;
let speechSupported = false;
let ttsSupported = false;
let isLoading = false;
let speechFinalBuffer = "";
let speechInterimBuffer = "";
let discardBufferedSpeech = false;
let isSpaceHeld = false;
let speechSynthesisRef = null;
let ttsVoices = [];
let selectedVoiceProfile = "en-female";

const VOICE_PROFILE_OPTIONS = [
  { value: "en-female", label: "English Female" },
  { value: "en-male", label: "English Male" },
  { value: "ne", label: "Nepali" },
];

const DEFAULT_READY_HINT =
  "Click Start Talking, speak, then click Stop Listening to send. You can also hold Spacebar.";
const LISTENING_HINT = "Listening... click Stop Listening to send.";

function initTextToSpeech() {
  if (!window.speechSynthesis || typeof window.SpeechSynthesisUtterance === "undefined") {
    ttsSupported = false;
    if (voiceSelect) {
      voiceSelect.disabled = true;
    }
    return;
  }

  speechSynthesisRef = window.speechSynthesis;
  ttsSupported = true;
  selectedVoiceProfile = getStoredVoiceProfile() || "en-female";
  if (voiceSelect) {
    voiceSelect.addEventListener("change", () => {
      selectedVoiceProfile = voiceSelect.value || "en-female";
      setStoredVoiceProfile(selectedVoiceProfile);
    });
  }

  const loadVoices = () => {
    ttsVoices = speechSynthesisRef.getVoices() || [];
    populateVoiceOptions();
  };

  loadVoices();
  speechSynthesisRef.addEventListener("voiceschanged", loadVoices);
}

function getStoredVoiceProfile() {
  return localStorage.getItem(TTS_PROFILE_KEY);
}

function setStoredVoiceProfile(profile) {
  localStorage.setItem(TTS_PROFILE_KEY, profile || "en-female");
}

function populateVoiceOptions() {
  if (!voiceSelect) {
    return;
  }

  for (const optionInfo of VOICE_PROFILE_OPTIONS) {
    const option = voiceSelect.querySelector(`option[value="${optionInfo.value}"]`);
    if (!option) {
      continue;
    }
    const matchedVoice = findVoiceByProfile(optionInfo.value);
    option.textContent = matchedVoice
      ? `${optionInfo.label} (${matchedVoice.name})`
      : `${optionInfo.label} (unavailable)`;
  }

  voiceSelect.disabled = false;
  voiceSelect.value = VOICE_PROFILE_OPTIONS.some((item) => item.value === selectedVoiceProfile)
    ? selectedVoiceProfile
    : "en-female";
  selectedVoiceProfile = voiceSelect.value;
  setStoredVoiceProfile(selectedVoiceProfile);
}

function findVoiceByProfile(profile) {
  if (!ttsVoices.length) {
    return null;
  }

  const englishVoices = ttsVoices.filter((voice) => voice.lang.toLowerCase().startsWith("en"));

  if (profile === "ne") {
    return (
      ttsVoices.find((voice) => voice.lang.toLowerCase().startsWith("ne")) ||
      ttsVoices.find((voice) => voice.name.toLowerCase().includes("nep")) ||
      null
    );
  }

  if (profile === "en-male") {
    return (
      englishVoices.find((voice) =>
        /(male|david|mark|guy|ryan|tom|james|george|daniel|richard)/i.test(voice.name)
      ) || englishVoices[0] || null
    );
  }

  return (
    englishVoices.find((voice) =>
      /(female|zira|jenny|aria|susan|sara|emma|olivia|linda|hazel|ava)/i.test(voice.name)
    ) || englishVoices[0] || null
  );
}

function speakText(text) {
  if (!ttsSupported || !speechSynthesisRef || !text || !text.trim()) {
    return;
  }

  speechSynthesisRef.cancel();
  const utterance = new SpeechSynthesisUtterance(text.trim());
  const selectedVoice = findVoiceByProfile(selectedVoiceProfile);
  if (selectedVoice) {
    utterance.voice = selectedVoice;
    utterance.lang = selectedVoice.lang;
  } else {
    utterance.lang = selectedVoiceProfile === "ne" ? "ne-NP" : "en-US";
  }
  utterance.rate = 1;
  utterance.pitch = 1;
  speechSynthesisRef.speak(utterance);
}

function togglePauseReplay() {
  if (!ttsSupported || !speechSynthesisRef) {
    return false;
  }

  if (!speechSynthesisRef.speaking) {
    return false;
  }

  if (speechSynthesisRef.paused) {
    speechSynthesisRef.resume();
    return true;
  }

  speechSynthesisRef.pause();
  return true;
}

function speakAssistantReply(text) {
  speakText(text);
}

function setVoiceState(listening) {
  if (!liveTranscript) {
    return;
  }

  isListening = listening;
  if (holdToTalkButton) {
    holdToTalkButton.classList.toggle("holding", listening);
    holdToTalkButton.textContent = listening ? "Stop Listening" : "Start Talking";
    holdToTalkButton.setAttribute(
      "aria-label",
      listening ? "Stop listening" : "Start talking"
    );
  }

  liveTranscript.textContent = listening ? LISTENING_HINT : DEFAULT_READY_HINT;
}

function updateTranscriptPreview(text) {
  if (!liveTranscript) {
    return;
  }

  if (!text || !text.trim()) {
    liveTranscript.textContent = isListening ? LISTENING_HINT : DEFAULT_READY_HINT;
    return;
  }

  liveTranscript.textContent = `Heard: ${text.trim()}`;
}

function startVoiceListening() {
  if (!speechSupported || !speechRecognition || isListening || isLoading || !currentUser) {
    return;
  }

  speechFinalBuffer = "";
  speechInterimBuffer = "";
  discardBufferedSpeech = false;

  try {
    speechRecognition.start();
  } catch {
    // Ignore start errors when browser reports an overlapping session.
  }
}

function stopVoiceListening(discard = false) {
  if (!speechRecognition || !isListening) {
    return;
  }

  discardBufferedSpeech = discard;
  try {
    speechRecognition.stop();
  } catch {
    // Ignore stop errors from race conditions.
  }
}

function toggleButtonListening() {
  if (isLoading || !currentUser) {
    return;
  }

  if (isListening) {
    stopVoiceListening(false);
    return;
  }

  startVoiceListening();
}

function isInteractiveTarget(target) {
  if (!target || !(target instanceof HTMLElement)) {
    return false;
  }

  const tag = target.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    tag === "BUTTON" ||
    target.isContentEditable
  );
}

function registerPushToTalkControls() {
  if (holdToTalkButton) {
    holdToTalkButton.textContent = "Start Talking";
    holdToTalkButton.setAttribute("aria-label", "Start talking");
    holdToTalkButton.addEventListener("click", () => {
      toggleButtonListening();
    });
  }

  document.addEventListener("keydown", (event) => {
    if (event.code !== "Space") {
      return;
    }

    if (event.repeat || isSpaceHeld) {
      return;
    }

    if (!currentUser || chatCard.classList.contains("hidden") || isInteractiveTarget(event.target)) {
      return;
    }

    isSpaceHeld = true;
    event.preventDefault();
    startVoiceListening();
  });

  document.addEventListener("keyup", (event) => {
    if (event.code !== "Space") {
      return;
    }

    if (!isSpaceHeld) {
      return;
    }

    isSpaceHeld = false;
    event.preventDefault();
    stopVoiceListening(false);
  });
}

function initVoiceInput() {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) {
    statusText.textContent = "Voice input is not supported in this browser.";
    if (liveTranscript) {
      liveTranscript.textContent = "Your browser does not support voice input.";
    }
    return;
  }

  speechSupported = true;
  speechRecognition = new Recognition();
  speechRecognition.lang = "en-US";
  speechRecognition.continuous = true;
  speechRecognition.interimResults = true;

  speechRecognition.onstart = () => {
    setVoiceState(true);
    statusText.textContent = "Listening...";
  };

  speechRecognition.onresult = (event) => {
    const finalTranscript = [];
    let interimTranscript = "";

    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const transcript = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        finalTranscript.push(transcript.trim());
      } else {
        interimTranscript += transcript;
      }
    }

    if (finalTranscript.length > 0) {
      speechFinalBuffer = `${speechFinalBuffer} ${finalTranscript.join(" ")}`.trim();
    }

    speechInterimBuffer = interimTranscript.trim();
    updateTranscriptPreview(speechInterimBuffer || speechFinalBuffer);
  };

  speechRecognition.onerror = () => {
    statusText.textContent = "Voice input error. Click Start Talking to try again.";
  };

  speechRecognition.onend = () => {
    setVoiceState(false);
    if (statusText.textContent !== "MindBridge is thinking..." && speechSupported) {
      statusText.textContent = "Ready";
    }

    const completedMessage = speechFinalBuffer.trim();
    speechFinalBuffer = "";
    speechInterimBuffer = "";

    if (discardBufferedSpeech || !completedMessage || isLoading || !currentUser) {
      discardBufferedSpeech = false;
      updateTranscriptPreview("");
      return;
    }

    updateTranscriptPreview(completedMessage);
    void processUserMessage(completedMessage);
  };
}

function clearChat() {
  chatWindow.innerHTML = "";
  history.length = 0;
}

function getStoredUserId() {
  const existing = localStorage.getItem(SESSION_USER_KEY);
  if (existing) {
    return existing;
  }

  return null;
}

function setStoredUserId(userId) {
  localStorage.setItem(SESSION_USER_KEY, userId);
}

function clearStoredUserId() {
  localStorage.removeItem(SESSION_USER_KEY);
}

function setAuthVisible(visible) {
  authCard.classList.toggle("hidden", !visible);
}

function setChatVisible(visible) {
  chatCard.classList.toggle("hidden", !visible);
}

function setUserBadge() {
  if (!currentUser) {
    userBadge.textContent = "Not logged in";
    return;
  }
  userBadge.textContent = `${currentUser.display_name} (@${currentUser.username})`;
}

function addMessage(role, content, riskLevel = null) {
  const node = messageTemplate.content.firstElementChild.cloneNode(true);
  node.classList.add(role);

  const roleLabel = node.querySelector(".role");
  const riskLabel = node.querySelector(".risk");
  const text = node.querySelector(".content");

  roleLabel.textContent = role === "user" ? "You" : "MindBridge";
  text.textContent = content;

  if (riskLevel) {
    riskLabel.textContent = `Risk: ${riskLevel}`;
    riskLabel.classList.add(riskLevel);
  } else {
    riskLabel.remove();
  }

  if (role === "assistant") {
    const actionRow = document.createElement("div");
    actionRow.className = "msg-actions";

    const rehearReplyButton = document.createElement("button");
    rehearReplyButton.type = "button";
    rehearReplyButton.className = "rehear-reply-btn";
    rehearReplyButton.textContent = "Rehear Reply";
    rehearReplyButton.setAttribute("aria-label", "Rehear this reply");
    rehearReplyButton.addEventListener("click", () => {
      speakText(content);
      pauseReplyButton.textContent = "Pause Replay";
      statusText.textContent = "Replaying assistant reply...";
    });

    const pauseReplyButton = document.createElement("button");
    pauseReplyButton.type = "button";
    pauseReplyButton.className = "pause-reply-btn";
    pauseReplyButton.textContent = "Pause Replay";
    pauseReplyButton.setAttribute("aria-label", "Pause or resume replay");
    pauseReplyButton.addEventListener("click", () => {
      const changed = togglePauseReplay();
      if (!changed) {
        statusText.textContent = "Nothing is playing right now.";
        pauseReplyButton.textContent = "Pause Replay";
        return;
      }

      if (speechSynthesisRef.paused) {
        pauseReplyButton.textContent = "Resume Replay";
        statusText.textContent = "Replay paused.";
      } else {
        pauseReplyButton.textContent = "Pause Replay";
        statusText.textContent = "Replay resumed.";
      }
    });

    actionRow.appendChild(rehearReplyButton);
    actionRow.appendChild(pauseReplyButton);
    node.appendChild(actionRow);
  }

  chatWindow.appendChild(node);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function setLoading(isLoading) {
  window.requestAnimationFrame(() => {
    statusText.textContent = isLoading ? "MindBridge is thinking..." : "Ready";
  });
}

function compactHistory() {
  return history.slice(-20);
}

async function sendMessage(message) {
  if (!currentUser) {
    throw new Error("Please login first.");
  }

  const payload = {
    user_id: currentUser.user_id,
    message,
    history: compactHistory(),
  };

  const response = await fetch("/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail = "Request failed.";
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch {
      // Keep generic fallback.
    }
    throw new Error(detail);
  }

  return response.json();
}

async function registerUser(displayName, username, password) {
  const response = await fetch("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ display_name: displayName, username, password }),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Registration failed.");
  }

  return data.user;
}

async function loginUser(username, password) {
  const response = await fetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Login failed.");
  }

  return data.user;
}

async function fetchUser(userId) {
  const response = await fetch(`/auth/user/${encodeURIComponent(userId)}`);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "User session invalid.");
  }

  return data.user;
}

async function fetchHistory(userId) {
  const response = await fetch(`/conversation/history/${encodeURIComponent(userId)}`);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Could not load conversation history.");
  }

  return data.history || [];
}

function bootstrapConversation() {
  clearChat();
  if (!currentUser) {
    return;
  }

  addMessage(
    "assistant",
    `Hi ${currentUser.display_name}, I am really glad you are here. How are you feeling today?`
  );
  speakAssistantReply(
    `Hi ${currentUser.display_name}, I am really glad you are here. How are you feeling today?`
  );
  history.push({
    role: "assistant",
    content: `Hi ${currentUser.display_name}, I am really glad you are here. How are you feeling today?`,
  });
}

function renderExistingHistory(existingHistory) {
  clearChat();
  for (const item of existingHistory) {
    if (item.role === "user" || item.role === "assistant") {
      addMessage(item.role, item.content);
      history.push({ role: item.role, content: item.content });
    }
  }
}

async function startSession(user) {
  currentUser = user;
  setStoredUserId(user.user_id);
  setUserBadge();
  setAuthVisible(false);
  setChatVisible(true);
  authStatus.textContent = `Logged in as ${user.display_name}.`;

  const existingHistory = await fetchHistory(user.user_id);
  if (existingHistory.length === 0) {
    bootstrapConversation();
  } else {
    renderExistingHistory(existingHistory);
  }
}

async function processUserMessage(message) {
  const cleanMessage = (message || "").trim();
  if (!cleanMessage || isLoading || !currentUser) {
    return;
  }

  isLoading = true;
  addMessage("user", cleanMessage);
  history.push({ role: "user", content: cleanMessage });
  setLoading(true);

  try {
    const data = await sendMessage(cleanMessage);
    addMessage("assistant", data.reply, data.risk_level);
    speakAssistantReply(data.reply);
    history.push({ role: "assistant", content: data.reply });
  } catch (error) {
    addMessage("assistant", `I ran into a connection issue: ${error.message}`);
    speakAssistantReply(`I ran into a connection issue: ${error.message}`);
  } finally {
    isLoading = false;
    setLoading(false);
    updateTranscriptPreview("");
  }
}

chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
});

logoutButton.addEventListener("click", () => {
  if (isListening && speechRecognition) {
    stopVoiceListening(true);
  }
  if (ttsSupported && speechSynthesisRef) {
    speechSynthesisRef.cancel();
  }
  currentUser = null;
  clearStoredUserId();
  setUserBadge();
  clearChat();
  setAuthVisible(true);
  setChatVisible(false);
  authStatus.textContent = "Logged out. Login with another user.";
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  authStatus.textContent = "Logging in...";
  try {
    const user = await loginUser(loginUsername.value.trim(), loginPassword.value.trim());
    await startSession(user);
  } catch (error) {
    authStatus.textContent = error.message;
  }
});

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  authStatus.textContent = "Creating account...";
  try {
    const user = await registerUser(
      registerDisplayName.value.trim(),
      registerUsername.value.trim(),
      registerPassword.value.trim()
    );
    await startSession(user);
  } catch (error) {
    authStatus.textContent = error.message;
  }
});

async function initialize() {
  setAuthVisible(true);
  setChatVisible(false);
  setUserBadge();
  initVoiceInput();
  initTextToSpeech();
  registerPushToTalkControls();

  const storedUserId = getStoredUserId();
  if (!storedUserId) {
    return;
  }

  try {
    authStatus.textContent = "Restoring session...";
    const user = await fetchUser(storedUserId);
    await startSession(user);
  } catch {
    clearStoredUserId();
    authStatus.textContent = "Session expired. Please login again.";
    setAuthVisible(true);
    setChatVisible(false);
  }
}

initialize();
