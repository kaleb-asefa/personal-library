const showMessage = (form, type, text) => {
    const message = form.querySelector("[data-form-message]");
    if (!message) return;

    message.hidden = false;
    message.className = `form-alert ${type}`;
    message.textContent = text;
};

const readJson = async (response) => {
    try {
        return await response.json();
    } catch {
        return {};
    }
};

const submitJson = async (url, payload) => {
    const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    const data = await readJson(response);

    if (!response.ok) {
        const message = data.message || data.detail || "Something went wrong.";
        throw new Error(typeof message === "string" ? message : "Validation error.");
    }

    return data;
};

const handleCreateUser = async (form) => {
    const formData = new FormData(form);
    const payload = {
        username: formData.get("username"),
        email: formData.get("email"),
        password: formData.get("password") || null,
    };

    const user = await submitJson("/api/users", payload);
    showMessage(form, "success", "User created.");
    window.setTimeout(() => {
        window.location.href = `/users/${user.user_id}`;
    }, 500);
};

const handleAddBook = async (form) => {
    const formData = new FormData(form);
    const genreIds = formData.getAll("genre_ids").map((value) => Number(value));

    if (!genreIds.length) {
        throw new Error("Choose at least one genre.");
    }

    const payload = {
        title: formData.get("title"),
        author_id: Number(formData.get("author_id")),
        published_year: Number(formData.get("published_year")),
        user_id: Number(formData.get("user_id")),
        genre_ids: genreIds,
    };

    const book = await submitJson("/api/books", payload);
    showMessage(form, "success", "Book added.");
    window.setTimeout(() => {
        window.location.href = `/users/${book.user_id}/books`;
    }, 500);
};

document.querySelectorAll("[data-api-form]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const submitButton = form.querySelector("button[type='submit']");
        const formType = form.dataset.apiForm;

        if (submitButton) submitButton.disabled = true;

        try {
            if (formType === "create-user") {
                await handleCreateUser(form);
            }

            if (formType === "add-book") {
                await handleAddBook(form);
            }
        } catch (error) {
            showMessage(form, "error", error.message);
        } finally {
            if (submitButton) submitButton.disabled = false;
        }
    });
});
