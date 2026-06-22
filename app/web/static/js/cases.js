const newCaseButton = document.getElementById("newCaseButton");
const caseEditor = document.getElementById("caseEditor");
const caseForm = document.getElementById("caseForm");
const cancelCaseButton = document.getElementById("cancelCaseButton");
const caseFormStatus = document.getElementById("caseFormStatus");

const caseIdInput = document.getElementById("caseId");
const caseTitleInput = document.getElementById("caseTitle");
const caseCategoryInput = document.getElementById("caseCategory");
const caseClientInput = document.getElementById("caseClient");
const caseOpponentInput = document.getElementById("caseOpponent");
const caseStatusInput = document.getElementById("caseStatus");
const caseDeadlineInput = document.getElementById("caseDeadline");
const caseNextActionInput = document.getElementById("caseNextAction");
const caseDescriptionInput = document.getElementById("caseDescription");

function openCaseEditor() {
  caseEditor.hidden = false;
  caseFormStatus.textContent = "";
  caseEditor.scrollIntoView({ behavior: "smooth", block: "start" });
}

function closeCaseEditor() {
  caseEditor.hidden = true;
  caseForm.reset();
  caseIdInput.value = "";
  caseFormStatus.textContent = "";
}

function fillCaseForm(card) {
  caseIdInput.value = card.dataset.caseId || "";
  caseTitleInput.value = card.dataset.title || "";
  caseClientInput.value = card.dataset.clientName || "";
  caseOpponentInput.value = card.dataset.opponentName || "";
  caseCategoryInput.value = card.dataset.category || "";
  caseStatusInput.value = card.dataset.status || "new";
  caseDescriptionInput.value = card.dataset.description || "";
  caseNextActionInput.value = card.dataset.nextAction || "";
  caseDeadlineInput.value = card.dataset.deadline || "";
}

function getCasePayload() {
  return {
    title: caseTitleInput.value.trim(),
    client_name: caseClientInput.value.trim(),
    opponent_name: caseOpponentInput.value.trim(),
    category: caseCategoryInput.value.trim(),
    status: caseStatusInput.value,
    deadline: caseDeadlineInput.value,
    next_action: caseNextActionInput.value.trim(),
    description: caseDescriptionInput.value.trim(),
  };
}

newCaseButton.addEventListener("click", () => {
  closeCaseEditor();
  openCaseEditor();
});

cancelCaseButton.addEventListener("click", () => {
  closeCaseEditor();
});

caseForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = getCasePayload();

  if (!payload.title) {
    caseFormStatus.textContent = "Название дела обязательно.";
    return;
  }

  const caseId = caseIdInput.value;
  const url = caseId ? `/api/cases/${caseId}` : "/api/cases";
  const method = caseId ? "PUT" : "POST";

  caseFormStatus.textContent = "Сохраняем дело...";

  try {
    const response = await fetch(url, {
      method,
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const data = await response.json();

    if (!response.ok || data.status !== "ok") {
      caseFormStatus.textContent = data.message || "Ошибка сохранения дела.";
      return;
    }

    window.location.reload();
  } catch (error) {
    caseFormStatus.textContent = "Ошибка соединения с сервером.";
  }
});

document.querySelectorAll(".edit-case-button").forEach((button) => {
  button.addEventListener("click", () => {
    const card = button.closest(".case-card");
    fillCaseForm(card);
    openCaseEditor();
  });
});

document.querySelectorAll(".delete-case-button").forEach((button) => {
  button.addEventListener("click", async () => {
    const card = button.closest(".case-card");
    const caseId = card.dataset.caseId;

    if (!caseId) {
      return;
    }

    const confirmed = window.confirm("Удалить это дело? Это действие нельзя отменить.");

    if (!confirmed) {
      return;
    }

    try {
      const response = await fetch(`/api/cases/${caseId}`, {
        method: "DELETE",
      });

      const data = await response.json();

      if (!response.ok || data.status !== "ok") {
        alert(data.message || "Ошибка удаления дела.");
        return;
      }

      window.location.reload();
    } catch (error) {
      alert("Ошибка соединения с сервером.");
    }
  });
});