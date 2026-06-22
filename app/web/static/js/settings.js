const lawyerProfileForm = document.getElementById("lawyerProfileForm");
const settingsStatus = document.getElementById("settingsStatus");

lawyerProfileForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const formData = new FormData(lawyerProfileForm);
  const payload = Object.fromEntries(formData.entries());

  settingsStatus.textContent = "Сохраняем профиль...";

  try {
    const response = await fetch("/api/settings/profile", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const data = await response.json();

    if (!response.ok || data.status !== "ok") {
      settingsStatus.textContent = data.message || "Ошибка сохранения.";
      return;
    }

    settingsStatus.textContent = "Профиль сохранён.";
  } catch (error) {
    settingsStatus.textContent = "Ошибка соединения с сервером.";
  }
});