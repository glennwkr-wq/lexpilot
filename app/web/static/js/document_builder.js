const documentStartScreen = document.getElementById("documentStartScreen");
const documentQuestionScreen = document.getElementById("documentQuestionScreen");
const documentPreviewScreen = document.getElementById("documentPreviewScreen");

const documentRequestInput = document.getElementById("documentRequest");
const builderClientIdInput = document.getElementById("builderClientId");
const builderCaseIdInput = document.getElementById("builderCaseId");

const generateDocumentButton = document.getElementById("generateDocumentButton");
const restartInterviewButton = document.getElementById("restartInterviewButton");
const backToInterviewButton = document.getElementById("backToInterviewButton");
const answerQuestionButton = document.getElementById("answerQuestionButton");
const skipQuestionButton = document.getElementById("skipQuestionButton");
const downloadDocumentButton = document.getElementById("downloadDocumentButton");
const downloadPdfButton = document.getElementById("downloadPdfButton");

const documentDraftBox = document.getElementById("documentDraftBox");
const documentStatusBadge = document.getElementById("documentStatusBadge");
const singleQuestionBox = document.getElementById("singleQuestionBox");

const signatureCanvas = document.getElementById("signatureCanvas");
const clearSignatureButton = document.getElementById("clearSignatureButton");

let currentDocumentDraft = "";
let currentDocumentTitle = "Юридический документ";
let currentClientName = "";
let currentExtractedData = {};
let currentQuestion = null;
let selectedTemplateId = "";
let interviewStarted = false;
let signaturePadReady = false;
let isDrawingSignature = false;

generateDocumentButton.addEventListener("click", async () => {
  selectedTemplateId = "";
  currentExtractedData = {};
  currentDocumentDraft = "";
  currentQuestion = null;
  interviewStarted = false;

  await runInterview({});
});

restartInterviewButton.addEventListener("click", () => {
  selectedTemplateId = "";
  currentExtractedData = {};
  currentDocumentDraft = "";
  currentQuestion = null;
  interviewStarted = false;

  showStartScreen();
});

backToInterviewButton.addEventListener("click", () => {
  showQuestionScreen();
});

answerQuestionButton.addEventListener("click", async () => {
  if (!currentQuestion) {
    showPreviewScreen();
    return;
  }

  const value = readCurrentQuestionValue();

  if (!value) {
    documentStatusBadge.textContent = "Введите ответ";
    return;
  }

  const answers = {};
  answers[currentQuestion.key] = value;

  await runInterview(answers);
});

skipQuestionButton.addEventListener("click", async () => {
  if (!currentQuestion) {
    return;
  }

  const answers = {};
  answers[currentQuestion.key] = `[УКАЗАТЬ: ${currentQuestion.label || currentQuestion.key}]`;

  await runInterview(answers);
});

downloadDocumentButton.addEventListener("click", async () => {
  if (!selectedTemplateId || !currentExtractedData) {
    documentStatusBadge.textContent = "Нет шаблона";
    return;
  }

  downloadDocumentButton.disabled = true;
  downloadDocumentButton.textContent = "Готовлю Word...";

  try {
    const response = await fetch("/api/document-builder/docx", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        content: currentDocumentDraft,
        title: currentDocumentTitle,
        client_name: currentClientName,
        template_id: selectedTemplateId,
        extracted_data: currentExtractedData,
        signature_data_url: getSignatureDataUrl(),
      }),
    });

    if (!response.ok) {
      documentStatusBadge.textContent = "Ошибка Word";
      return;
    }

    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = downloadUrl;
    link.download = `${sanitizeFilename(currentDocumentTitle)}.docx`;
    document.body.appendChild(link);
    link.click();
    link.remove();

    window.URL.revokeObjectURL(downloadUrl);
    documentStatusBadge.textContent = "Word скачан";
  } catch (error) {
    documentStatusBadge.textContent = "Ошибка скачивания";
  } finally {
    downloadDocumentButton.disabled = false;
    downloadDocumentButton.textContent = "Скачать Word";
  }
});

async function runInterview(answers) {
  const requestText = documentRequestInput.value.trim();

  if (!requestText) {
    documentRequestInput.focus();
    return;
  }

  setLoading(true);
  showQuestionScreen();
  renderQuestionLoading();

  try {
    const response = await fetch("/api/document-builder", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        request: requestText,
        client_id: builderClientIdInput ? builderClientIdInput.value : "",
        case_id: builderCaseIdInput ? builderCaseIdInput.value : "",
        previous_data: currentExtractedData,
        answers: answers || {},
        selected_template_id: selectedTemplateId,
      }),
    });

    const data = await response.json();

    if (!response.ok || data.status !== "ok") {
      singleQuestionBox.innerHTML = `
        <div class="single-question-card">
          <span>Ошибка</span>
          <strong>${escapeHtml(data.message || "Ошибка генерации.")}</strong>
        </div>
      `;
      documentStatusBadge.textContent = "Ошибка";
      return;
    }

    interviewStarted = true;

    selectedTemplateId = data.selected_template?.id || selectedTemplateId;
    currentDocumentDraft = data.draft || "";
    currentDocumentTitle = data.selected_template?.title || data.detected_label || "Юридический документ";
    currentClientName = data.client?.full_name || getSelectedClientName();
    currentExtractedData = data.extracted_data || {};
    currentQuestion = data.current_question || null;

    if (currentQuestion) {
      documentStatusBadge.textContent = "Вопрос";
      renderQuestion(currentQuestion);
      answerQuestionButton.disabled = false;
    } else {
      documentStatusBadge.textContent = "Документ готов";
      renderPreview();
      showPreviewScreen();
    }

    downloadDocumentButton.disabled = !selectedTemplateId;
  } catch (error) {
    singleQuestionBox.innerHTML = `
      <div class="single-question-card">
        <span>Ошибка</span>
        <strong>Ошибка соединения с сервером.</strong>
      </div>
    `;
    documentStatusBadge.textContent = "Ошибка";
  } finally {
    setLoading(false);
  }
}

function renderQuestionLoading() {
  if (skipQuestionButton) {
    skipQuestionButton.hidden = true;
  }
  singleQuestionBox.innerHTML = `
    <div class="single-question-card">
      <span>LexPilot</span>
      <strong>Подбираю следующий вопрос...</strong>
      <p>Система проверяет уже заполненные данные и российский Word-шаблон.</p>
    </div>
  `;
}

function renderQuestion(question) {
  if (skipQuestionButton) {
    skipQuestionButton.hidden = false;
  }
  const type = question.type || "text";
  const options = Array.isArray(question.options) ? question.options : [];

  let control = "";

  if (type === "textarea") {
    control = `<textarea id="singleQuestionInput" placeholder="${escapeHtml(question.placeholder || "")}"></textarea>`;
  } else if (type === "choice" && options.length > 0) {
    control = `
      <div class="interview-choice-list">
        ${options.map((option) => `
          <button type="button" class="interview-choice-button" data-choice-value="${escapeHtml(option.value || option)}">
            ${escapeHtml(option.label || option.value || option)}
          </button>
        `).join("")}
      </div>
      <input id="singleQuestionInput" type="hidden" />
    `;
  } else {
    control = `<input id="singleQuestionInput" type="text" placeholder="${escapeHtml(question.placeholder || "")}" />`;
  }

  singleQuestionBox.innerHTML = `
    <div class="single-question-card">
      <span>Следующий вопрос</span>
      <strong>${escapeHtml(question.label || question.key)}</strong>
      ${question.help ? `<p>${escapeHtml(question.help)}</p>` : ""}
      ${control}
    </div>
  `;

  const input = document.getElementById("singleQuestionInput");

  document.querySelectorAll(".interview-choice-button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".interview-choice-button").forEach((item) => {
        item.classList.remove("is-selected");
      });

      button.classList.add("is-selected");

      if (input) {
        input.value = button.dataset.choiceValue || "";
      }
    });
  });

  if (input && type !== "choice") {
    input.focus();
    input.addEventListener("keydown", async (event) => {
      if (event.key === "Enter" && type !== "textarea") {
        event.preventDefault();
        answerQuestionButton.click();
      }
    });
  }
}

function readCurrentQuestionValue() {
  const input = document.getElementById("singleQuestionInput");

  if (!input) {
    return "";
  }

  return input.value.trim();
}

function renderPreview() {
  documentDraftBox.innerHTML = `<pre class="document-draft-text">${escapeHtml(currentDocumentDraft || "Документ готов к скачиванию в Word.")}</pre>`;
  downloadDocumentButton.disabled = !selectedTemplateId;
  downloadPdfButton.disabled = true;
  initSignaturePad();
}

function showStartScreen() {
  documentStartScreen.classList.remove("is-hidden");
  documentQuestionScreen.classList.add("is-hidden");
  documentPreviewScreen.classList.add("is-hidden");

  documentStatusBadge.textContent = "Ожидает данные";
  generateDocumentButton.disabled = false;
  generateDocumentButton.textContent = "Начать интервью";
}

function showQuestionScreen() {
  documentStartScreen.classList.add("is-hidden");
  documentQuestionScreen.classList.remove("is-hidden");
  documentPreviewScreen.classList.add("is-hidden");
}

function showPreviewScreen() {
  documentStartScreen.classList.add("is-hidden");
  documentQuestionScreen.classList.add("is-hidden");
  documentPreviewScreen.classList.remove("is-hidden");
  initSignaturePad();
}

function setLoading(isLoading) {
  generateDocumentButton.disabled = isLoading;
  answerQuestionButton.disabled = isLoading || !currentQuestion;
  skipQuestionButton.disabled = isLoading || !currentQuestion;
  generateDocumentButton.textContent = isLoading
    ? "Обработка..."
    : "Начать интервью";

  answerQuestionButton.textContent = isLoading
    ? "Обработка..."
    : "Продолжить";
}

function initSignaturePad() {
  if (!signatureCanvas || signaturePadReady) {
    return;
  }

  signaturePadReady = true;

  const context = signatureCanvas.getContext("2d");
  context.lineWidth = 2;
  context.lineCap = "round";
  context.strokeStyle = "#111827";

  const getPoint = (event) => {
    const rect = signatureCanvas.getBoundingClientRect();
    const source = event.touches ? event.touches[0] : event;

    return {
      x: source.clientX - rect.left,
      y: source.clientY - rect.top,
    };
  };

  const startDrawing = (event) => {
    event.preventDefault();
    isDrawingSignature = true;

    const point = getPoint(event);
    context.beginPath();
    context.moveTo(point.x, point.y);
  };

  const draw = (event) => {
    if (!isDrawingSignature) {
      return;
    }

    event.preventDefault();

    const point = getPoint(event);
    context.lineTo(point.x, point.y);
    context.stroke();
  };

  const stopDrawing = () => {
    isDrawingSignature = false;
  };

  signatureCanvas.addEventListener("mousedown", startDrawing);
  signatureCanvas.addEventListener("mousemove", draw);
  signatureCanvas.addEventListener("mouseup", stopDrawing);
  signatureCanvas.addEventListener("mouseleave", stopDrawing);

  signatureCanvas.addEventListener("touchstart", startDrawing);
  signatureCanvas.addEventListener("touchmove", draw);
  signatureCanvas.addEventListener("touchend", stopDrawing);

  if (clearSignatureButton) {
    clearSignatureButton.addEventListener("click", () => {
      context.clearRect(0, 0, signatureCanvas.width, signatureCanvas.height);
    });
  }
}

function getSignatureDataUrl() {
  if (!signatureCanvas) {
    return "";
  }

  const context = signatureCanvas.getContext("2d");
  const pixels = context.getImageData(0, 0, signatureCanvas.width, signatureCanvas.height).data;

  for (let index = 3; index < pixels.length; index += 4) {
    if (pixels[index] !== 0) {
      return signatureCanvas.toDataURL("image/png");
    }
  }

  return "";
}

function getSelectedClientName() {
  if (!builderClientIdInput || !builderClientIdInput.value) {
    return "";
  }

  const selectedOption = builderClientIdInput.options[builderClientIdInput.selectedIndex];

  return selectedOption ? selectedOption.textContent.trim() : "";
}

function sanitizeFilename(value) {
  return value
    .trim()
    .replace(/[\\/:*?"<>|]+/g, "_")
    .replace(/\s+/g, "_")
    .slice(0, 80) || "document";
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}