// Copy-link button for the "open in your browser" hint. No network calls.
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("[data-copy-url]").forEach(function (button) {
    button.addEventListener("click", function () {
      var url = button.getAttribute("data-copy-url");
      var field = document.getElementById("copy-url");

      function fallback() {
        // Clipboard unavailable: select the read-only field so it can be copied by long-press.
        if (field) {
          field.focus();
          field.select();
        }
      }

      if (!navigator.clipboard || !navigator.clipboard.writeText) {
        fallback();
        return;
      }
      navigator.clipboard.writeText(url).then(function () {
        button.textContent = button.getAttribute("data-copied-label");
      }, fallback);
    });
  });
});
