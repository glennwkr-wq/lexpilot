const documentRequestInput = document.getElementById("documentRequest");
const builderClientIdInput = document.getElementById("builderClientId");
const builderCaseIdInput = document.getElementById("builderCaseId");
const generateDocumentButton = document.getElementById("generateDocumentButton");
const answerQuestionButton = document.getElementById("answerQuestionButton");
const downloadDocumentButton = document.getElementById("downloadDocumentButton");
const documentDraftBox = document.getElementById("documentDraftBox");
const documentSourcesBox = document.getElementById("documentSourcesBox");
const documentStatusBadge = document.getElementById("documentStatusBadge");
const interviewProgressBox = document.getElementById("interviewProgressBox");
const singleQuestionBox = document.getElementById("singleQuestionBox");
const templateChoiceBox = document.getElementById("templateChoiceBox");

let currentDocumentDraft = "";
let currentDocumentTitle = "Юридический документ";
let currentClientName = "";
let currentExtractedData = {};
let currentQuestion = null;
let selectedTemplateId = "";
let interviewStarted = false;

generateDocumentButton.addEventListener("click", async () => {
  selectedTemplateId = "";
  currentExtractedData = {};
  await runInterview({});
});

answerQuestionButton.addEventListener("click", async () => {
  if (!currentQuestion) {
    return;
  }

  const input = document.getElementById("singleQuestionInput");

  if (!input) {
    return;
  }

  const value = input.value.trim();

  if (!value) {
    documentStatusBadge.textContent = "Введите ответ";
    return;
  }

  const answers = {};
  answers[currentQuestion.key] = value;

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
    documentDraftBox.textContent = "Введите, какой документ нужно подготовить.";
    documentStatusBadge.textContent = "Нет данных";
    return;
  }

  setLoading(true);

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
      documentDraftBox.textContent = data.message || "Ошибка генерации.";
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

    renderTemplateChoices(data.candidate_templates || []);
    renderProgress(data);
    renderQuestion(currentQuestion);
    renderSources(data.sources || []);

    documentDraftBox.innerHTML = `<pre class="document-draft-text">${escapeHtml(currentDocumentDraft)}</pre>`;

    if (currentQuestion) {
      documentStatusBadge.textContent = "Нужен ответ";
      answerQuestionButton.disabled = false;
    } else {
      documentStatusBadge.textContent = "Готов к Word";
      answerQuestionButton.disabled = true;
    }

    downloadDocumentButton.disabled = !selectedTemplateId;
  } catch (error) {
    documentDraftBox.textContent = "Ошибка соединения с сервером.";
    documentStatusBadge.textContent = "Ошибка";
  } finally {
    setLoading(false);
  }
}

function renderTemplateChoices(templates) {
  if (!templateChoiceBox) {
    return;
  }

  if (!templates || templates.length <= 1) {
    templateChoiceBox.classList.add("is-hidden");
    templateChoiceBox.innerHTML = "";
    return;
  }

  templateChoiceBox.classList.remove("is-hidden");

  templateChoiceBox.innerHTML = `
    <strong>Похожие шаблоны</strong>
    <div class="template-choice-list">
      ${templates.map((template) => {
        const active = template.id === selectedTemplateId ? "is-active" : "";

        return `
          <button type="button" class="template-choice-item ${active}" data-template-id="${escapeHtml(template.id)}">
            <span>${escapeHtml(template.title)}</span>
            <small>${escapeHtml(template.category || "")}${template.subcategory ? " · " + escapeHtml(template.subcategory) : ""}</small>
          </button>
        `;
      }).join("")}
    </div>
  `;

  templateChoiceBox.querySelectorAll("[data-template-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      selectedTemplateId = button.dataset.templateId || "";
      currentExtractedData = {};
      await runInterview({});
    });
  });
}

function renderProgress(data) {
  const completeness = data.completeness || {};
  const template = data.selected_template || {};
  const fields = data.extracted_data?.fields || {};
  const filledCount = Object.values(fields).filter((value) => value && value !== "не указано").length;

  interviewProgressBox.innerHTML = `
    <div class="interview-progress-grid">
      <div>
        <span>Шаблон</span>
        <strong>${escapeHtml(template.title || "Не выбран")}</strong>
      </div>
      <div>
        <span>Заполненность</span>
        <strong>${Number(completeness.percent || 0)}%</strong>
      </div>
      <div>
        <span>Заполнено полей</span>
        <strong>${filledCount}</strong>
      </div>
    </div>
  `;
}

function renderQuestion(question) {
  if (!singleQuestionBox) {
    return;
  }

  if (!question) {
    singleQuestionBox.classList.remove("is-hidden");
    singleQuestionBox.innerHTML = `
      <div class="single-question-card">
        <span>Интервью завершено</span>
        <strong>Все обязательные данные заполнены или отмечены плейсхолдерами.</strong>
        <p>Можно скачать Word и проверить документ.</p>
      </div>
    `;
    return;
  }

  singleQuestionBox.classList.remove("is-hidden");

  const type = question.type || "text";

  const control = type === "textarea"
    ? `<textarea id="singleQuestionInput" placeholder="${escapeHtml(question.placeholder || "")}"></textarea>`
    : `<input id="singleQuestionInput" type="text" placeholder="${escapeHtml(question.placeholder || "")}" />`;

  singleQuestionBox.innerHTML = `
    <div class="single-question-card">
      <span>Следующий вопрос</span>
      <strong>${escapeHtml(question.label || question.key)}</strong>
      ${question.help ? `<p>${escapeHtml(question.help)}</p>` : ""}
      ${control}
    </div>
  `;

  const input = document.getElementById("singleQuestionInput");

  if (input) {
    input.focus();
    input.addEventListener("keydown", async (event) => {
      if (event.key === "Enter" && type !== "textarea") {
        event.preventDefault();
        answerQuestionButton.click();
      }
    });
  }
}

function renderSources(sources) {
  if (!sources || sources.length === 0) {
    documentSourcesBox.innerHTML = "Шаблон не найден.";
    return;
  }

  documentSourcesBox.innerHTML = sources.map((source, index) => {
    return `
      <div class="source-item">
        <strong>${index + 1}. ${escapeHtml(source.title || "Шаблон")}</strong>
        <span>${escapeHtml(source.document_type || "")}</span>
        ${source.source_url ? `<small>${escapeHtml(source.source_url)}</small>` : ""}
      </div>
    `;
  }).join("");
}

function setLoading(isLoading) {
  generateDocumentButton.disabled = isLoading;
  answerQuestionButton.disabled = isLoading || !currentQuestion;

  generateDocumentButton.textContent = isLoading
    ? "Обработка..."
    : interviewStarted
      ? "Перезапустить"
      : "Начать";
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