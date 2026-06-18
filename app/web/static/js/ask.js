const questionInput = document.getElementById("question");
const askButton = document.getElementById("askButton");
const answerBox = document.getElementById("answerBox");
const sourcesBox = document.getElementById("sourcesBox");
const statusBadge = document.getElementById("statusBadge");

function setLoading(isLoading) {
  askButton.disabled = isLoading;
  askButton.textContent = isLoading ? "LexPilot думает..." : "Получить ответ";
  statusBadge.textContent = isLoading ? "Обработка" : "Готово";
}

function renderSources(sources) {
  if (!sources || sources.length === 0) {
    sourcesBox.innerHTML = "<p>Релевантные источники в базе знаний не найдены.</p>";
    return;
  }

  sourcesBox.innerHTML = sources
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

askButton.addEventListener("click", async () => {
  const question = questionInput.value.trim();

  if (!question) {
    answerBox.textContent = "Введите вопрос.";
    statusBadge.textContent = "Нет вопроса";
    return;
  }

  setLoading(true);
  answerBox.textContent = "Идёт поиск по базе знаний и подготовка ответа...";
  sourcesBox.textContent = "Поиск источников...";

  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ question }),
    });

    const data = await response.json();

    if (!response.ok || data.status !== "ok") {
      answerBox.textContent = data.message || "Ошибка при обработке запроса.";
      statusBadge.textContent = "Ошибка";
      return;
    }

    answerBox.textContent = data.answer || "Ответ пустой.";
    renderSources(data.sources);
    statusBadge.textContent = "Ответ готов";
  } catch (error) {
    answerBox.textContent = "Ошибка соединения с сервером.";
    sourcesBox.textContent = "";
    statusBadge.textContent = "Ошибка";
  } finally {
    setLoading(false);
  }
});