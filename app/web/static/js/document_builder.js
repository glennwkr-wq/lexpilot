const documentRequestInput = document.getElementById("documentRequest");
const documentQuestionsPanel = document.getElementById("documentQuestionsPanel");
const documentQuestionsBox = document.getElementById("documentQuestionsBox");
const builderClientIdInput = document.getElementById("builderClientId");
const builderCaseIdInput = document.getElementById("builderCaseId");
const generateDocumentButton = document.getElementById("generateDocumentButton");
const downloadDocumentButton = document.getElementById("downloadDocumentButton");
const documentDraftBox = document.getElementById("documentDraftBox");
const documentSourcesBox = document.getElementById("documentSourcesBox");
const documentStatusBadge = document.getElementById("documentStatusBadge");

let currentDocumentDraft = "";
let currentDocumentTitle = "Юридический документ";
let currentClientName = "";
let currentDocumentFamily = "";
let currentExtractedData = {};
let currentMissingFieldAnswers = {};

function setDocumentLoading(isLoading) {
  generateDocumentButton.disabled = isLoading;
  generateDocumentButton.textContent = isLoading
    ? "LexPilot собирает данные..."
    : "Сформировать документ";

  if (isLoading) {
    documentStatusBadge.textContent = "Проверка данных";
  }
}

function renderDocumentMeta(data) {
  const label = data.detected_label || buildDocumentTitle(data);
  const completeness = data.completeness || {};
  const missingFields = data.missing_required_fields || [];
  const extractedData = data.extracted_data || {};
  const fields = extractedData.fields || {};

  const filledFields = Object.entries(fields)
    .filter(([, value]) => value && value !== "не указано")
    .slice(0, 8);

  const filledHtml = filledFields.length
    ? filledFields
        .map(([key, value]) => `<li><strong>${escapeHtml(key)}:</strong> ${escapeHtml(String(value))}</li>`)
        .join("")
    : "<li>LexPilot не нашел явно заполненных полей.</li>";

  const missingHtml = missingFields.length
    ? missingFields
        .map((field) => `<li>${escapeHtml(field.label || field.key)}</li>`)
        .join("")
    : "<li>Критичных пропусков по обязательным полям не найдено.</li>";

  return `
    <div class="document-meta-panel">
      <div class="document-meta-grid">
        <div>
          <span class="meta-label">Тип документа</span>
          <strong>${escapeHtml(label)}</strong>
        </div>
        <div>
          <span class="meta-label">Заполненность</span>
          <strong>${Number(completeness.percent || 0)}%</strong>
        </div>
        <div>
          <span class="meta-label">Статус</span>
          <strong>${escapeHtml(completeness.label || "Проверка выполнена")}</strong>
        </div>
      </div>

      <div class="document-check-grid">
        <div>
          <h4>Найденные данные</h4>
          <ul>${filledHtml}</ul>
        </div>
        <div>
          <h4>Чего не хватает</h4>
          <ul>${missingHtml}</ul>
        </div>
      </div>
    </div>
  `;
}

function renderDocumentSources(sources) {
  if (!sources || sources.length === 0) {
    documentSourcesBox.innerHTML = "<p>Релевантные материалы базы знаний не найдены.</p>";
    return;
  }

  documentSourcesBox.innerHTML = sources
    .slice(0, 5)
    .map((source, index) => {
      return `
        <div class="source-item">
          <strong>${index + 1}. ${escapeHtml(source.title || "Без названия")}</strong>
          <span>${escapeHtml(source.document_type || "Материал базы")}</span>
        </div>
      `;
    })
    .join("");
}

generateDocumentButton.addEventListener("click", async () => {
  const requestText = documentRequestInput.value.trim();

  const additionalText = buildStructuredAnswersText();

  if (!requestText) {
    documentDraftBox.textContent = "Введите исходные данные для документа.";
    documentStatusBadge.textContent = "Нет данных";
    return;
  }

  currentDocumentDraft = "";
  currentDocumentTitle = "Юридический документ";
  currentClientName = getSelectedClientName();
  currentDocumentFamily = "";
  currentExtractedData = {};

  if (downloadDocumentButton) {
    downloadDocumentButton.disabled = true;
  }

  setDocumentLoading(true);
  documentDraftBox.textContent = "Идёт определение типа документа, извлечение данных и подготовка черновика...";
  documentSourcesBox.textContent = "Поиск материалов...";

  try {
    const response = await fetch("/api/document-builder", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        request: buildCombinedRequest(requestText, additionalText),
        client_id: builderClientIdInput ? builderClientIdInput.value : "",
        case_id: builderCaseIdInput ? builderCaseIdInput.value : "",
      }),
    });

    const data = await response.json();

    if (!response.ok || data.status !== "ok") {
      documentDraftBox.textContent = data.message || "Ошибка при генерации документа.";
      documentStatusBadge.textContent = "Ошибка";
      return;
    }

    currentDocumentDraft = data.draft || "";
    currentDocumentTitle = data.detected_label || buildDocumentTitle(data);
    currentClientName = data.client?.full_name || getSelectedClientName();
    currentDocumentFamily = data.detected_family || "";
    currentExtractedData = data.extracted_data || {};
    renderDocumentQuestions(data.missing_required_fields || []);

    documentDraftBox.innerHTML = `
      ${renderDocumentMeta(data)}
      <pre class="document-draft-text">${escapeHtml(currentDocumentDraft || "Документ не был сформирован.")}</pre>
    `;

    renderDocumentSources(data.sources);

    const completeness = data.completeness || {};
    const missingCount = Number(completeness.missing_count || 0);

    if (data.saved_document) {
      documentStatusBadge.textContent = "Черновик сохранён в дело";
    } else if (missingCount > 0) {
      documentStatusBadge.textContent = "Нужны уточнения";
    } else {
      documentStatusBadge.textContent = "Черновик готов";
    }

    if (downloadDocumentButton) {
      downloadDocumentButton.disabled = !currentDocumentDraft;
    }
  } catch (error) {
    documentDraftBox.textContent = "Ошибка соединения с сервером.";
    documentSourcesBox.textContent = "";
    documentStatusBadge.textContent = "Ошибка";
  } finally {
    setDocumentLoading(false);
  }
});

if (downloadDocumentButton) {
  downloadDocumentButton.addEventListener("click", async () => {
    if (!currentDocumentDraft) {
      documentStatusBadge.textContent = "Нет документа";
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
          body: JSON.stringify({
          content: currentDocumentDraft,
          title: currentDocumentTitle,
          client_name: currentClientName,
        }),
      });

      if (!response.ok) {
        documentStatusBadge.textContent = "Ошибка DOCX";
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

function buildCombinedRequest(requestText, additionalText) {
  if (!additionalText) {
    return requestText;
  }

  return `
ИСХОДНЫЙ ЗАПРОС:
${requestText}

ДОПОЛНИТЕЛЬНЫЕ ДАННЫЕ ОТ ПОЛЬЗОВАТЕЛЯ:
${additionalText}

ЗАДАЧА:
С учётом дополнительных данных повторно проверь обязательные данные и подготовь более полный черновик документа.
`.trim();
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

function renderDocumentQuestions(missingFields) {
  if (!documentQuestionsPanel || !documentQuestionsBox) {
    return;
  }

  if (!missingFields || missingFields.length === 0) {
    documentQuestionsPanel.classList.add("is-hidden");
    documentQuestionsBox.innerHTML = "";
    return;
  }

  documentQuestionsPanel.classList.remove("is-hidden");

  documentQuestionsBox.innerHTML = missingFields
    .map((field) => {
      const key = field.key || "";
      const label = field.label || key;
      const savedValue = currentMissingFieldAnswers[key] || "";

      return `
        <label class="document-question-item">
          <span>${escapeHtml(label)}</span>
          <input
            type="text"
            data-missing-field-key="${escapeHtml(key)}"
            value="${escapeHtml(savedValue)}"
            placeholder="Введите значение, если известно"
          />
        </label>
      `;
    })
    .join("");

  documentQuestionsBox
    .querySelectorAll("[data-missing-field-key]")
    .forEach((input) => {
      input.addEventListener("input", () => {
        currentMissingFieldAnswers[input.dataset.missingFieldKey] = input.value.trim();
      });
    });
}

function buildStructuredAnswersText() {
  if (!documentQuestionsBox) {
    return "";
  }

  const inputs = documentQuestionsBox.querySelectorAll("[data-missing-field-key]");
  const lines = [];

  inputs.forEach((input) => {
    const key = input.dataset.missingFieldKey || "";
    const value = input.value.trim();

    if (!value) {
      return;
    }

    currentMissingFieldAnswers[key] = value;
    lines.push(`${key}: ${value}`);
  });

  if (lines.length === 0) {
    return "";
  }

  return `
ОТВЕТЫ НА УТОЧНЯЮЩИЕ ВОПРОСЫ:
${lines.join("\n")}
`.trim();
}