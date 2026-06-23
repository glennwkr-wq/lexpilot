const knowledgeForm = document.getElementById("knowledgeForm");
const knowledgeResetButton = document.getElementById("knowledgeResetButton");
const knowledgeFormStatus = document.getElementById("knowledgeFormStatus");
const knowledgeSearchInput = document.getElementById("knowledgeSearchInput");
const knowledgeOriginFilter = document.getElementById("knowledgeOriginFilter");
const knowledgeDocumentsList = document.getElementById("knowledgeDocumentsList");
const knowledgeNoResults = document.getElementById("knowledgeNoResults");

function setKnowledgeStatus(message, isError = false) {
  if (!knowledgeFormStatus) {
    return;
  }

  knowledgeFormStatus.textContent = message;
  knowledgeFormStatus.classList.toggle("error-text", isError);
  knowledgeFormStatus.classList.toggle("success-text", !isError);
}

if (knowledgeForm) {
  knowledgeForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const submitButton = knowledgeForm.querySelector("button[type='submit']");
    const formData = new FormData(knowledgeForm);

    const payload = {
      document_type: formData.get("document_type"),
      title: formData.get("title"),
      source_url: formData.get("source_url"),
      document_date: formData.get("document_date"),
      content: formData.get("content"),
    };

    if (submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = "Сохраняю...";
    }

    setKnowledgeStatus("Материал сохраняется в базу знаний...");

    try {
      const response = await fetch("/api/knowledge/manual", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      const result = await response.json();

      if (!response.ok || result.status !== "ok") {
        throw new Error(result.message || "Не удалось сохранить материал.");
      }

      setKnowledgeStatus(
        `Материал сохранён. Создано фрагментов поиска: ${result.document.chunks_count}.`
      );

      setTimeout(() => {
        window.location.reload();
      }, 900);
    } catch (error) {
      setKnowledgeStatus(error.message, true);
    } finally {
      if (submitButton) {
        submitButton.disabled = false;
        submitButton.textContent = "Сохранить в базу знаний";
      }
    }
  });
}

if (knowledgeResetButton && knowledgeForm) {
  knowledgeResetButton.addEventListener("click", () => {
    knowledgeForm.reset();
    setKnowledgeStatus(
      "Не добавляйте непроверенные нормы, неподтверждённую практику и персональные данные."
    );
  });
}

function applyKnowledgeFilters() {
  if (!knowledgeDocumentsList) {
    return;
  }

  const query = (knowledgeSearchInput?.value || "").trim().toLowerCase();
  const origin = knowledgeOriginFilter?.value || "all";

  const items = Array.from(
    knowledgeDocumentsList.querySelectorAll(".knowledge-doc-item")
  );

  let visibleCount = 0;

  items.forEach((item) => {
    const searchText = item.dataset.search || "";
    const itemOrigin = item.dataset.origin || "system";

    const matchesQuery = !query || searchText.includes(query);
    const matchesOrigin = origin === "all" || itemOrigin === origin;

    const shouldShow = matchesQuery && matchesOrigin;

    item.classList.toggle("knowledge-hidden", !shouldShow);

    if (shouldShow) {
      visibleCount += 1;
    }
  });

  if (knowledgeNoResults) {
    knowledgeNoResults.classList.toggle("knowledge-hidden", visibleCount > 0);
  }
}

if (knowledgeSearchInput) {
  knowledgeSearchInput.addEventListener("input", applyKnowledgeFilters);
}

if (knowledgeOriginFilter) {
  knowledgeOriginFilter.addEventListener("change", applyKnowledgeFilters);
}