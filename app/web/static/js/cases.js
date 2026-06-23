const newCaseButton = document.getElementById("newCaseButton");
const caseEditor = document.getElementById("caseEditor");
const caseForm = document.getElementById("caseForm");
const cancelCaseButton = document.getElementById("cancelCaseButton");
const caseFormStatus = document.getElementById("caseFormStatus");

const caseIdInput = document.getElementById("caseId");
const caseTitleInput = document.getElementById("caseTitle");
const caseCategoryInput = document.getElementById("caseCategory");
const caseClientIdInput = document.getElementById("caseClientId");
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
  caseClientIdInput.value = card.dataset.clientId || "";
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
    client_id: caseClientIdInput.value,
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

const newTaskButton = document.getElementById("newTaskButton");
const taskEditor = document.getElementById("taskEditor");
const taskForm = document.getElementById("taskForm");
const cancelTaskButton = document.getElementById("cancelTaskButton");
const taskFormStatus = document.getElementById("taskFormStatus");

const taskIdInput = document.getElementById("taskId");
const taskTitleInput = document.getElementById("taskTitle");
const taskCaseIdInput = document.getElementById("taskCaseId");
const taskDueDateInput = document.getElementById("taskDueDate");
const taskPriorityInput = document.getElementById("taskPriority");
const taskStatusInput = document.getElementById("taskStatus");
const taskDescriptionInput = document.getElementById("taskDescription");

function openTaskEditor() {
  taskEditor.hidden = false;
  taskFormStatus.textContent = "";
  taskEditor.scrollIntoView({ behavior: "smooth", block: "start" });
}

function closeTaskEditor() {
  taskEditor.hidden = true;
  taskForm.reset();
  taskIdInput.value = "";
  taskFormStatus.textContent = "";
}

function fillTaskForm(card) {
  taskIdInput.value = card.dataset.taskId || "";
  taskTitleInput.value = card.dataset.title || "";
  taskCaseIdInput.value = card.dataset.caseId || "";
  taskDueDateInput.value = card.dataset.dueDate || "";
  taskPriorityInput.value = card.dataset.priority || "normal";
  taskStatusInput.value = card.dataset.status || "open";
  taskDescriptionInput.value = card.dataset.description || "";
}

function getTaskPayload() {
  return {
    title: taskTitleInput.value.trim(),
    case_id: taskCaseIdInput.value,
    due_date: taskDueDateInput.value,
    priority: taskPriorityInput.value,
    status: taskStatusInput.value,
    description: taskDescriptionInput.value.trim(),
  };
}

newTaskButton.addEventListener("click", () => {
  closeTaskEditor();
  openTaskEditor();
});

cancelTaskButton.addEventListener("click", () => {
  closeTaskEditor();
});

taskForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = getTaskPayload();

  if (!payload.title) {
    taskFormStatus.textContent = "Название задачи обязательно.";
    return;
  }

  const taskId = taskIdInput.value;
  const url = taskId ? `/api/tasks/${taskId}` : "/api/tasks";
  const method = taskId ? "PUT" : "POST";

  taskFormStatus.textContent = "Сохраняем задачу...";

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
      taskFormStatus.textContent = data.message || "Ошибка сохранения задачи.";
      return;
    }

    window.location.reload();
  } catch (error) {
    taskFormStatus.textContent = "Ошибка соединения с сервером.";
  }
});

document.querySelectorAll(".edit-task-button").forEach((button) => {
  button.addEventListener("click", () => {
    const card = button.closest(".task-card");
    fillTaskForm(card);
    openTaskEditor();
  });
});

document.querySelectorAll(".delete-task-button").forEach((button) => {
  button.addEventListener("click", async () => {
    const card = button.closest(".task-card");
    const taskId = card.dataset.taskId;

    if (!taskId) {
      return;
    }

    const confirmed = window.confirm("Удалить эту задачу? Это действие нельзя отменить.");

    if (!confirmed) {
      return;
    }

    try {
      const response = await fetch(`/api/tasks/${taskId}`, {
        method: "DELETE",
      });

      const data = await response.json();

      if (!response.ok || data.status !== "ok") {
        alert(data.message || "Ошибка удаления задачи.");
        return;
      }

      window.location.reload();
    } catch (error) {
      alert("Ошибка соединения с сервером.");
    }
  });
});

const workspaceSearchInput = document.getElementById("workspaceSearchInput");
const workspaceTypeFilter = document.getElementById("workspaceTypeFilter");
const workspaceStatusFilter = document.getElementById("workspaceStatusFilter");

function applyWorkspaceFilters() {
  const searchValue = workspaceSearchInput
    ? workspaceSearchInput.value.trim().toLowerCase()
    : "";

  const typeValue = workspaceTypeFilter
    ? workspaceTypeFilter.value
    : "all";

  const statusValue = workspaceStatusFilter
    ? workspaceStatusFilter.value
    : "all";

  document.querySelectorAll(".compact-record").forEach((card) => {
    const text = card.textContent.toLowerCase();
    const recordType = card.dataset.recordType || "";
    const status = card.dataset.status || "";

    const matchesSearch = !searchValue || text.includes(searchValue);
    const matchesType = typeValue === "all" || recordType === typeValue;
    const matchesStatus = statusValue === "all" || status === statusValue;

    card.hidden = !(matchesSearch && matchesType && matchesStatus);
  });
}

if (workspaceSearchInput) {
  workspaceSearchInput.addEventListener("input", applyWorkspaceFilters);
}

if (workspaceTypeFilter) {
  workspaceTypeFilter.addEventListener("change", applyWorkspaceFilters);
}

if (workspaceStatusFilter) {
  workspaceStatusFilter.addEventListener("change", applyWorkspaceFilters);
}