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
    sourcesBox.innerHTML = "<p>Релевантные федеральные источники не найдены.</p>";
    return;
  }
  sources = sources.slice(0, 5);
  sourcesBox.innerHTML = sources
    .map((source, index) => {
      const groupLabel =
        source.source_group === "federal_law"
          ? "Федеральный корпус RusLawOD"
          : "Локальная база LexPilot";

      const numberText = source.document_number
        ? `№ ${escapeHtml(source.document_number)}`
        : "номер не указан";

      const dateText = source.document_date
        ? escapeHtml(source.document_date)
        : "дата не указана";

      const authorityText = source.authority
        ? escapeHtml(source.authority)
        : "орган не указан";

      const statusText = source.status
        ? escapeHtml(source.status)
        : "статус не указан";

      const rankText = source.rank
        ? ` • релевантность ${Number(source.rank).toFixed(2)}`
        : "";

      return `
        <div class="source-item">
          <strong>${index + 1}. ${escapeHtml(source.title || "Без названия")}</strong>
          <span>${escapeHtml(source.document_type || "тип не указан")} · ${numberText} · ${dateText}</span>
          <small>${groupLabel}${rankText}</small>
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

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}