const analysisFileInput = document.getElementById("analysisFileInput");
const extractAnalysisFileButton = document.getElementById("extractAnalysisFileButton");
const documentTextInput = document.getElementById("documentText");
const analysisCaseIdInput = document.getElementById("analysisCaseId");
const analyzeDocumentButton = document.getElementById("analyzeDocumentButton");
const documentAnalysisBox = document.getElementById("documentAnalysisBox");
const analysisSourcesBox = document.getElementById("analysisSourcesBox");
const analysisStatusBadge = document.getElementById("analysisStatusBadge");

function setAnalysisLoading(isLoading) {
  analyzeDocumentButton.disabled = isLoading;
  analyzeDocumentButton.textContent = isLoading
    ? "LexPilot анализирует..."
    : "Проанализировать документ";
  analysisStatusBadge.textContent = isLoading ? "Анализ" : "Готово";
}

if (extractAnalysisFileButton) {
  extractAnalysisFileButton.addEventListener("click", async () => {
    const file = analysisFileInput?.files?.[0];

    if (!file) {
      documentAnalysisBox.textContent = "Выберите PDF, DOCX или TXT файл.";
      analysisStatusBadge.textContent = "Нет файла";
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    extractAnalysisFileButton.disabled = true;
    extractAnalysisFileButton.textContent = "Извлекаю текст...";
    analysisStatusBadge.textContent = "Чтение файла";

    try {
      const response = await fetch("/api/document-analysis/upload", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok || data.status !== "ok") {
        documentAnalysisBox.textContent = data.message || "Не удалось прочитать файл.";
        analysisStatusBadge.textContent = "Ошибка файла";
        return;
      }

      documentTextInput.value = data.text || "";
      documentAnalysisBox.textContent = `Текст извлечён из файла: ${data.filename}`;
      analysisStatusBadge.textContent = "Текст готов";
    } catch (error) {
      documentAnalysisBox.textContent = "Ошибка загрузки файла.";
      analysisStatusBadge.textContent = "Ошибка";
    } finally {
      extractAnalysisFileButton.disabled = false;
      extractAnalysisFileButton.textContent = "Извлечь текст из файла";
    }
  });
}

function renderAnalysisSources(sources) {
  if (!sources || sources.length === 0) {
    analysisSourcesBox.innerHTML = "<p>Релевантные материалы базы знаний не найдены.</p>";
    return;
  }

  analysisSourcesBox.innerHTML = sources
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

analyzeDocumentButton.addEventListener("click", async () => {
  const documentText = documentTextInput.value.trim();

  if (!documentText) {
    documentAnalysisBox.textContent = "Вставьте текст документа или загрузите файл.";
    analysisStatusBadge.textContent = "Нет данных";
    return;
  }

  setAnalysisLoading(true);
  documentAnalysisBox.textContent = "Идёт анализ документа...";
  analysisSourcesBox.textContent = "Поиск материалов...";

  try {
    const response = await fetch("/api/document-analysis", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        document_text: documentText,
        case_id: analysisCaseIdInput ? analysisCaseIdInput.value : "",
      }),
    });

    const data = await response.json();

    if (!response.ok || data.status !== "ok") {
      documentAnalysisBox.textContent = data.message || "Ошибка при анализе документа.";
      analysisStatusBadge.textContent = "Ошибка";
      return;
    }

    documentAnalysisBox.textContent = data.analysis || "Анализ не был сформирован.";
    renderAnalysisSources(data.sources);
    analysisStatusBadge.textContent = "Анализ готов";
    if (data.saved_analysis) {
      analysisStatusBadge.textContent = "Анализ сохранён в дело";
    }
  } catch (error) {
    documentAnalysisBox.textContent = "Ошибка соединения с сервером.";
    analysisSourcesBox.textContent = "";
    analysisStatusBadge.textContent = "Ошибка";
  } finally {
    setAnalysisLoading(false);
  }
});