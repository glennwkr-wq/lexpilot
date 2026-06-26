const documentRequestInput = document.getElementById("documentRequest");
const builderClientIdInput = document.getElementById("builderClientId");
const builderCaseIdInput = document.getElementById("builderCaseId");
const generateDocumentButton = document.getElementById("generateDocumentButton");
const downloadDocumentButton = document.getElementById("downloadDocumentButton");
const documentDraftBox = document.getElementById("documentDraftBox");
const documentSourcesBox = document.getElementById("documentSourcesBox");
const documentStatusBadge = document.getElementById("documentStatusBadge");
const interviewProgressBox = document.getElementById("interviewProgressBox");
const interviewQuestionsPanel = document.getElementById("interviewQuestionsPanel");
const interviewQuestionsBox = document.getElementById("interviewQuestionsBox");

let currentDocumentDraft = "";
let currentDocumentTitle = "Юридический документ";
let currentClientName = "";
let currentDocumentFamily = "";
let currentExtractedData = {};
let currentVisibleFields = [];
let currentMissingFields = [];
let interviewStarted = false;

function setDocumentLoading(isLoading) {
  generateDocumentButton.disabled = isLoading;
  generateDocumentButton.textContent = isLoading
    ? "LexPilot обновляет интервью..."
    : interviewStarted
      ? "Обновить документ"
      : "Начать интервью";

  if (isLoading) {
    documentStatusBadge.textContent = "Обработка";
  }
}

generateDocumentButton.addEventListener("click", async () => {
  const requestText = documentRequestInput.value.trim();

  if (!requestText) {
    documentDraftBox.textContent = "Введите задачу юриста.";
    documentStatusBadge.textContent = "Нет данных";
    return;
  }

  const answers = collectInterviewAnswers();

  setDocumentLoading(true);
  documentDraftBox.textContent = "LexPilot проверяет данные интервью...";
  documentSourcesBox.textContent = "Проверка материалов...";
  interviewProgressBox.textContent = "Идёт обработка...";

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
        answers: answers,
        document_family: currentDocumentFamily,
      }),
    });

    const data = await response.json();

    if (!response.ok || data.status !== "ok") {
      documentDraftBox.textContent = data.message || "Ошибка при генерации документа.";
      documentStatusBadge.textContent = "Ошибка";
      return;
    }

    interviewStarted = true;

    currentDocumentDraft = data.draft || "";
    currentDocumentTitle = data.detected_label || buildDocumentTitle(data);
    currentClientName = data.client?.full_name || getSelectedClientName();
    currentDocumentFamily = data.detected_family || "";
    currentExtractedData = data.extracted_data || {};
    currentVisibleFields = data.visible_fields || [];
    currentMissingFields = data.missing_required_fields || [];

    renderInterviewProgress(data);
    renderInterviewQuestions(currentVisibleFields, currentExtractedData.fields || {});
    renderDocumentSources(data.sources);

    documentDraftBox.innerHTML = `
      <pre class="document-draft-text">${escapeHtml(currentDocumentDraft || "Документ не был сформирован.")}</pre>
    `;

    const missingCount = Number(data.completeness?.missing_count || 0);

    if (data.saved_document) {
      documentStatusBadge.textContent = "Сохранён в дело";
    } else if (missingCount > 0) {
      documentStatusBadge.textContent = "Нужны данные";
    } else {
      documentStatusBadge.textContent = "Готов к Word";
    }

    if (downloadDocumentButton) {
      downloadDocumentButton.disabled = false;
    }
  } catch (error) {
    documentDraftBox.textContent = "Ошибка соединения с сервером.";
    documentSourcesBox.textContent = "";
    interviewProgressBox.textContent = "";
    documentStatusBadge.textContent = "Ошибка";
  } finally {
    setDocumentLoading(false);
  }
});

if (downloadDocumentButton) {
  downloadDocumentButton.addEventListener("click", async () => {
    if (!currentDocumentFamily || !currentExtractedData) {
      documentStatusBadge.textContent = "Нет данных";
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
          document_family: currentDocumentFamily,
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
}

function renderInterviewProgress(data) {
  const completeness = data.completeness || {};
  const template = data.docx_template || {};
  const missingFields = data.missing_required_fields || [];
  const extractedData = data.extracted_data || {};
  const fields = extractedData.fields || {};

  const filledCount = Object.values(fields).filter((value) => {
    return value && value !== "не указано";
  }).length;

  const templateStatus = template.available
    ? `Word-шаблон найден: ${template.filename}`
    : "Word-шаблон не найден, будет использован fallback";

  const missingText = missingFields.length
    ? missingFields.map((field) => `<li>${escapeHtml(field.label || field.key)}</li>`).join("")
    : "<li>Критичных пропусков нет.</li>";

  interviewProgressBox.innerHTML = `
    <div class="interview-progress-grid">
      <div>
        <span>Тип документа</span>
        <strong>${escapeHtml(data.detected_label || buildDocumentTitle(data))}</strong>
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

    <div class="interview-template-status">
      ${escapeHtml(templateStatus)}
    </div>

    <div class="interview-missing-box">
      <strong>Чего не хватает</strong>
      <ul>${missingText}</ul>
    </div>
  `;
}

function renderInterviewQuestions(fields, values) {
  if (!interviewQuestionsPanel || !interviewQuestionsBox) {
    return;
  }

  if (!fields || fields.length === 0) {
    interviewQuestionsPanel.classList.add("is-hidden");
    interviewQuestionsBox.innerHTML = "";
    return;
  }

  interviewQuestionsPanel.classList.remove("is-hidden");

  interviewQuestionsBox.innerHTML = fields
    .map((field) => {
      const key = field.key || "";
      const label = field.label || key;
      const help = field.help || "";
      const type = field.type || "text";
      const placeholder = field.placeholder || "";
      const value = values[key] || "";

      return buildQuestionInput({
        key,
        label,
        help,
        type,
        placeholder,
        value,
        choices: field.choices || [],
        required: Boolean(field.required),
      });
    })
    .join("");
}

function buildQuestionInput(field) {
  const requiredMark = field.required ? "<em>обязательно</em>" : "<em>желательно</em>";
  const helpHtml = field.help ? `<small>${escapeHtml(field.help)}</small>` : "";

  if (field.type === "textarea") {
    return `
      <label class="interview-question-item">
        <span>${escapeHtml(field.label)} ${requiredMark}</span>
        ${helpHtml}
        <textarea
          data-interview-field="${escapeHtml(field.key)}"
          placeholder="${escapeHtml(field.placeholder)}"
        >${escapeHtml(field.value)}</textarea>
      </label>
    `;
  }

  if (field.type === "select" && field.choices && field.choices.length > 0) {
    const options = field.choices
      .map((choice) => {
        const selected = String(choice) === String(field.value) ? "selected" : "";

        return `<option value="${escapeHtml(choice)}" ${selected}>${escapeHtml(choice)}</option>`;
      })
      .join("");

    return `
      <label class="interview-question-item">
        <span>${escapeHtml(field.label)} ${requiredMark}</span>
        ${helpHtml}
        <select data-interview-field="${escapeHtml(field.key)}">
          <option value="">Не выбрано</option>
          ${options}
        </select>
      </label>
    `;
  }

  return `
    <label class="interview-question-item">
      <span>${escapeHtml(field.label)} ${requiredMark}</span>
      ${helpHtml}
      <input
        type="${field.type === "date" ? "date" : "text"}"
        data-interview-field="${escapeHtml(field.key)}"
        value="${escapeHtml(field.value)}"
        placeholder="${escapeHtml(field.placeholder)}"
      />
    </label>
  `;
}

function collectInterviewAnswers() {
  if (!interviewQuestionsBox) {
    return {};
  }

  const controls = interviewQuestionsBox.querySelectorAll("[data-interview-field]");
  const answers = {};

  controls.forEach((control) => {
    const key = control.dataset.interviewField || "";
    const value = control.value.trim();

    if (key && value) {
      answers[key] = value;
    }
  });

  return answers;
}

function renderDocumentSources(sources) {
  if (!sources || sources.length === 0) {
    documentSourcesBox.innerHTML = "<p>Материалы не найдены.</p>";
    return;
  }

  documentSourcesBox.innerHTML = sources
    .slice(0, 5)
    .map((source, index) => {
      return `
        <div class="source-item">
          <strong>${index + 1}. ${escapeHtml(source.title || "Без названия")}</strong>
          <span>${escapeHtml(source.document_type || "Материал")}</span>
          ${source.source_url ? `<small>${escapeHtml(source.source_url)}</small>` : ""}
        </div>
      `;
    })
    .join("");
}

function getSelectedClientName() {
  if (!builderClientIdInput || !builderClientIdInput.value) {
    return "";
  }

  const selectedOption = builderClientIdInput.options[builderClientIdInput.selectedIndex];

  return selectedOption ? selectedOption.textContent.trim() : "";
}

function buildDocumentTitle(data) {
  if (data.detected_family === "claim") {
    return "Претензия";
  }

  if (data.detected_family === "lawsuit") {
    return "Исковое заявление";
  }

  if (data.detected_family === "motion") {
    return "Ходатайство";
  }

  if (data.detected_family === "response") {
    return "Отзыв или возражения";
  }

  if (data.detected_family === "appeal") {
    return "Апелляционная жалоба";
  }

  if (data.detected_family === "cassation") {
    return "Кассационная жалоба";
  }

  if (data.detected_family === "complaint") {
    return "Жалоба";
  }

  return "Юридический документ";
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