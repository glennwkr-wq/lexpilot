const knowledgeForm = document.getElementById("knowledgeForm");
const knowledgeResetButton = document.getElementById("knowledgeResetButton");
const knowledgeFormStatus = document.getElementById("knowledgeFormStatus");
const knowledgeSearchInput = document.getElementById("knowledgeSearchInput");
const knowledgeOriginFilter = document.getElementById("knowledgeOriginFilter");
const knowledgeDocumentsList = document.getElementById("knowledgeDocumentsList");
const knowledgeNoResults = document.getElementById("knowledgeNoResults");
const knowledgeShowMoreButton = document.getElementById("knowledgeShowMoreButton");

const KNOWLEDGE_PAGE_SIZE = 12;
let knowledgeVisibleLimit = KNOWLEDGE_PAGE_SIZE;

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

function getKnowledgeItems() {
  if (!knowledgeDocumentsList) {
    return [];
  }

  return Array.from(
    knowledgeDocumentsList.querySelectorAll(".knowledge-compact-item")
  );
}

function getFilteredKnowledgeItems() {
  const query = (knowledgeSearchInput?.value || "").trim().toLowerCase();
  const origin = knowledgeOriginFilter?.value || "all";

  return getKnowledgeItems().filter((item) => {
    const searchText = item.dataset.search || "";
    const itemOrigin = item.dataset.origin || "system";

    const matchesQuery = !query || searchText.includes(query);
    const matchesOrigin = origin === "all" || itemOrigin === origin;

    return matchesQuery && matchesOrigin;
  });
}

function applyKnowledgeFilters() {
  const allItems = getKnowledgeItems();

  if (!allItems.length) {
    return;
  }

  const filteredItems = getFilteredKnowledgeItems();
  const filteredSet = new Set(filteredItems);

  let visibleCount = 0;

  allItems.forEach((item) => {
    const isFiltered = filteredSet.has(item);
    const shouldShow =
      isFiltered && visibleCount < knowledgeVisibleLimit;

    item.classList.toggle("knowledge-hidden", !shouldShow);

    if (shouldShow) {
      visibleCount += 1;
    }
  });

  if (knowledgeNoResults) {
    knowledgeNoResults.classList.toggle("knowledge-hidden", filteredItems.length > 0);
  }

  if (knowledgeShowMoreButton) {
    const shouldShowButton = filteredItems.length > knowledgeVisibleLimit;
    knowledgeShowMoreButton.classList.toggle("knowledge-hidden", !shouldShowButton);
  }
}

function resetKnowledgeLimitAndApply() {
  knowledgeVisibleLimit = KNOWLEDGE_PAGE_SIZE;
  applyKnowledgeFilters();
}

if (knowledgeSearchInput) {
  knowledgeSearchInput.addEventListener("input", resetKnowledgeLimitAndApply);
}

if (knowledgeOriginFilter) {
  knowledgeOriginFilter.addEventListener("change", resetKnowledgeLimitAndApply);
}

if (knowledgeShowMoreButton) {
  knowledgeShowMoreButton.addEventListener("click", () => {
    knowledgeVisibleLimit += KNOWLEDGE_PAGE_SIZE;
    applyKnowledgeFilters();
  });
}

applyKnowledgeFilters();