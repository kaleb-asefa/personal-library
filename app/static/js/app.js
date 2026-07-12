// Progressive enhancement only. All core flows (auth, add/edit book)
// work via plain HTML form posts + redirects, with or without this file.

document.addEventListener("submit", (event) => {
    const form = event.target;
    const message = form.dataset.confirm;
    if (!message) return;

    if (!window.confirm(message.replace(/&ldquo;/g, "\u201C").replace(/&rdquo;/g, "\u201D"))) {
        event.preventDefault();
    }
});
