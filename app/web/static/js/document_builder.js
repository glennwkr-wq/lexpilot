const documentRequestInput = document.getElementById("documentRequest");
const generateDocumentButton = document.getElementById("generateDocumentButton");
const documentDraftBox = document.getElementById("documentDraftBox");
const documentSourcesBox = document.getElementById("documentSourcesBox");
const documentStatusBadge = document.getElementById("documentStatusBadge");

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

  if (!requestText) {
    documentDraftBox.textContent = "Введите исходные данные для документа.";
    documentStatusBadge.textContent = "Нет данных";
    return;
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
      body: JSON.stringify({ request: requestText }),
    });

    const data = await response.json();

    if (!response.ok || data.status !== "ok") {
      documentDraftBox.textContent = data.message || "Ошибка при генерации документа.";
      documentStatusBadge.textContent = "Ошибка";
      return;
    }

    documentDraftBox.textContent = data.draft || "Документ не был сформирован.";
    renderDocumentSources(data.sources);
    documentStatusBadge.textContent = "Черновик готов";
  } catch (error) {
    documentDraftBox.textContent = "Ошибка соединения с сервером.";
    documentSourcesBox.textContent = "";
    documentStatusBadge.textContent = "Ошибка";
  } finally {
    setDocumentLoading(false);
  }
});