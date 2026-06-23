const documentRequestInput = document.getElementById("documentRequest");
const additionalDocumentDataInput = document.getElementById("additionalDocumentData");
const builderClientIdInput = document.getElementById("builderClientId");
const generateDocumentButton = document.getElementById("generateDocumentButton");
const downloadDocumentButton = document.getElementById("downloadDocumentButton");
const documentDraftBox = document.getElementById("documentDraftBox");
const documentSourcesBox = document.getElementById("documentSourcesBox");
const documentStatusBadge = document.getElementById("documentStatusBadge");

let currentDocumentDraft = "";
let currentDocumentTitle = "Юридический документ";
let currentClientName = "";

function setDocumentLoading(isLoading) {
  generateDocumentButton.disabled = isLoading;
  generateDocumentButton.textContent = isLoading
    ? "LexPilot готовит документ..."
    : "Сформировать документ";
  documentStatusBadge.textContent = isLoading ? "Генерация" : "Готово";
}

function renderDocumentSources(sources) {
  if (!sources || sources.length === 0) {
    documentSourcesBox.innerHTML = "<p>Релевантные материалы базы знаний не найдены.</p>";
    return;
  }

  documentSourcesBox.innerHTML = sources
    .map((source, index) => {
      return `
        <div class="source-item">
          <strong>${index + 1}. ${source.title || "Без названия"}</strong>
          <span>${source.document_type || "unknown"}</span>
          <small>${source.source_url || ""}</small>
        </div>
      `;
    })
    .join("");
}

generateDocumentButton.addEventListener("click", async () => {
  const requestText = documentRequestInput.value.trim();

  const additionalText = additionalDocumentDataInput
    ? additionalDocumentDataInput.value.trim()
    : "";

  if (!requestText) {
    documentDraftBox.textContent = "Введите исходные данные для документа.";
    documentStatusBadge.textContent = "Нет данных";
    return;
  }

  currentDocumentDraft = "";
  currentDocumentTitle = "Юридический документ";
  currentClientName = getSelectedClientName();

  if (downloadDocumentButton) {
    downloadDocumentButton.disabled = true;
  }

  setDocumentLoading(true);
  documentDraftBox.textContent = "Идёт поиск по базе знаний и подготовка черновика...";
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
      }),
    });

    const data = await response.json();

    if (!response.ok || data.status !== "ok") {
      documentDraftBox.textContent = data.message || "Ошибка при генерации документа.";
      documentStatusBadge.textContent = "Ошибка";
      return;
    }

    currentDocumentDraft = data.draft || "";
    currentDocumentTitle = buildDocumentTitle(data);
    currentClientName = data.client?.full_name || getSelectedClientName();

    documentDraftBox.textContent = currentDocumentDraft || "Документ не был сформирован.";
    renderDocumentSources(data.sources);
    documentStatusBadge.textContent = "Черновик готов";

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