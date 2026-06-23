const newClientButton = document.getElementById("newClientButton");
const clientEditor = document.getElementById("clientEditor");
const clientForm = document.getElementById("clientForm");
const cancelClientButton = document.getElementById("cancelClientButton");
const clientFormStatus = document.getElementById("clientFormStatus");

const clientIdInput = document.getElementById("clientId");
const clientTypeInput = document.getElementById("clientType");
const clientFullNameInput = document.getElementById("clientFullName");
const clientShortNameInput = document.getElementById("clientShortName");
const clientPhoneInput = document.getElementById("clientPhone");
const clientEmailInput = document.getElementById("clientEmail");
const clientAddressInput = document.getElementById("clientAddress");
const clientInnInput = document.getElementById("clientInn");
const clientOgrnInput = document.getElementById("clientOgrn");
const clientPassportInput = document.getElementById("clientPassport");
const clientRepresentativeInput = document.getElementById("clientRepresentative");
const clientNotesInput = document.getElementById("clientNotes");

const clientSearchInput = document.getElementById("clientSearchInput");
const clientTypeFilter = document.getElementById("clientTypeFilter");
const clientsNoResults = document.getElementById("clientsNoResults");

function openClientEditor() {
  clientEditor.hidden = false;
  clientFormStatus.textContent = "";
  clientEditor.scrollIntoView({ behavior: "smooth", block: "start" });
}

function closeClientEditor() {
  clientEditor.hidden = true;
  clientForm.reset();
  clientIdInput.value = "";
  clientFormStatus.textContent = "";
}

function fillClientForm(card) {
  clientIdInput.value = card.dataset.clientId || "";
  clientTypeInput.value = card.dataset.clientType || "person";
  clientFullNameInput.value = card.dataset.fullName || "";
  clientShortNameInput.value = card.dataset.shortName || "";
  clientPhoneInput.value = card.dataset.phone || "";
  clientEmailInput.value = card.dataset.email || "";
  clientAddressInput.value = card.dataset.address || "";
  clientInnInput.value = card.dataset.inn || "";
  clientOgrnInput.value = card.dataset.ogrn || "";
  clientPassportInput.value = card.dataset.passportDetails || "";
  clientRepresentativeInput.value = card.dataset.representative || "";
  clientNotesInput.value = card.dataset.notes || "";
}

function getClientPayload() {
  return {
    client_type: clientTypeInput.value,
    full_name: clientFullNameInput.value.trim(),
    short_name: clientShortNameInput.value.trim(),
    phone: clientPhoneInput.value.trim(),
    email: clientEmailInput.value.trim(),
    address: clientAddressInput.value.trim(),
    inn: clientInnInput.value.trim(),
    ogrn: clientOgrnInput.value.trim(),
    passport_details: clientPassportInput.value.trim(),
    representative: clientRepresentativeInput.value.trim(),
    notes: clientNotesInput.value.trim(),
  };
}

if (newClientButton) {
  newClientButton.addEventListener("click", () => {
    closeClientEditor();
    openClientEditor();
  });
}

if (cancelClientButton) {
  cancelClientButton.addEventListener("click", () => {
    closeClientEditor();
  });
}

if (clientForm) {
  clientForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const payload = getClientPayload();

    if (!payload.full_name) {
      clientFormStatus.textContent = "ФИО или наименование клиента обязательно.";
      return;
    }

    const clientId = clientIdInput.value;
    const url = clientId ? `/api/clients/${clientId}` : "/api/clients";
    const method = clientId ? "PUT" : "POST";

    clientFormStatus.textContent = "Сохраняем клиента...";

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
        clientFormStatus.textContent = data.message || "Ошибка сохранения клиента.";
        return;
      }

      window.location.reload();
    } catch (error) {
      clientFormStatus.textContent = "Ошибка соединения с сервером.";
    }
  });
}

document.querySelectorAll(".edit-client-button").forEach((button) => {
  button.addEventListener("click", () => {
    const card = button.closest(".client-card");
    fillClientForm(card);
    openClientEditor();
  });
});

document.querySelectorAll(".delete-client-button").forEach((button) => {
  button.addEventListener("click", async () => {
    const card = button.closest(".client-card");
    const clientId = card.dataset.clientId;

    if (!clientId) {
      return;
    }

    const confirmed = window.confirm("Удалить этого клиента? Это действие нельзя отменить.");

    if (!confirmed) {
      return;
    }

    try {
      const response = await fetch(`/api/clients/${clientId}`, {
        method: "DELETE",
      });

      const data = await response.json();

      if (!response.ok || data.status !== "ok") {
        alert(data.message || "Ошибка удаления клиента.");
        return;
      }

      window.location.reload();
    } catch (error) {
      alert("Ошибка соединения с сервером.");
    }
  });
});

function applyClientFilters() {
  const searchValue = clientSearchInput
    ? clientSearchInput.value.trim().toLowerCase()
    : "";

  const typeValue = clientTypeFilter
    ? clientTypeFilter.value
    : "all";

  let visibleCount = 0;

  document.querySelectorAll(".client-card").forEach((card) => {
    const text = card.textContent.toLowerCase();
    const clientType = card.dataset.clientType || "";

    const matchesSearch = !searchValue || text.includes(searchValue);
    const matchesType = typeValue === "all" || clientType === typeValue;

    const shouldShow = matchesSearch && matchesType;

    card.hidden = !shouldShow;

    if (shouldShow) {
      visibleCount += 1;
    }
  });

  if (clientsNoResults) {
    clientsNoResults.hidden = visibleCount > 0;
  }
}

if (clientSearchInput) {
  clientSearchInput.addEventListener("input", applyClientFilters);
}

if (clientTypeFilter) {
  clientTypeFilter.addEventListener("change", applyClientFilters);
}

applyClientFilters();