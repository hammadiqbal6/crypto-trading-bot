(() => {
  // Subtle presence: fade-in panels already in CSS; add form busy state
  document.querySelectorAll("form[data-busy]").forEach((form) => {
    form.addEventListener("submit", () => {
      form.classList.add("loading");
      const btn = form.querySelector("button,[type=submit]");
      if (btn) {
        btn.dataset.label = btn.textContent;
        btn.textContent = "Working…";
        btn.disabled = true;
      }
    });
  });
})();
