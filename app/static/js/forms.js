const showMessage = (form, type, text) => {
    const message = form.querySelector("[data-form-message]");
    if (!message) return;

    message.hidden = false;
    message.className = `form-alert ${type}`;
    message.textContent = text;
};

const AUTH_STORAGE_KEYS = {
    token: "reading-shelf.access-token",
    user: "reading-shelf.current-user",
};

const readStoredAuth = () => {
    const token = window.localStorage.getItem(AUTH_STORAGE_KEYS.token);
    const userRaw = window.localStorage.getItem(AUTH_STORAGE_KEYS.user);

    let user = null;

    if (userRaw) {
        try {
            user = JSON.parse(userRaw);
        } catch {
            user = null;
        }
    }

    return { token, user };
};

const saveAuth = ({ token, user }) => {
    if (token) {
        window.localStorage.setItem(AUTH_STORAGE_KEYS.token, token);
    }

    if (user) {
        window.localStorage.setItem(AUTH_STORAGE_KEYS.user, JSON.stringify(user));
    }
};

const clearAuth = () => {
    window.localStorage.removeItem(AUTH_STORAGE_KEYS.token);
    window.localStorage.removeItem(AUTH_STORAGE_KEYS.user);
};

const getAuthHeaders = () => {
    const { token } = readStoredAuth();
    return token ? { Authorization: `Bearer ${token}` } : {};
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

const submitFormUrlEncoded = async (url, payload) => {
    const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams(payload).toString(),
    });
    const data = await readJson(response);

    if (!response.ok) {
        const message = data.message || data.detail || "Something went wrong.";
        throw new Error(typeof message === "string" ? message : "Validation error.");
    }

    return data;
};

const updateJson = async (url, payload) => {
    const response = await fetch(url, {
        method: "PATCH",
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

const deleteJson = async (url) => {
    const response = await fetch(url, { method: "DELETE" });

    if (!response.ok) {
        const data = await readJson(response);
        const message = data.message || data.detail || "Something went wrong.";
        throw new Error(typeof message === "string" ? message : "Delete failed.");
    }
};

const getActiveNavHref = (pathname) => {
    if (pathname === "/login") return "/login";
    if (pathname === "/logout") return "/logout";
    if (pathname === "/users/new") return "/users/new";
    if (pathname === "/books/new") return "/books/new";
    if (pathname.startsWith("/books/")) return "/";
    if (pathname.startsWith("/users")) return "/users";
    return "/";
};

const updateActiveNav = () => {
    const activeHref = getActiveNavHref(window.location.pathname);

    document.querySelectorAll("[data-nav-link]").forEach((link) => {
        const isActive = link.getAttribute("href") === activeHref;
        link.classList.toggle("is-active", isActive);

        if (isActive) {
            link.setAttribute("aria-current", "page");
        } else {
            link.removeAttribute("aria-current");
        }
    });
};

const visitPage = (url) => {
    const pageContent = document.querySelector("#page-content");

    if (window.htmx && pageContent) {
        window.htmx.ajax("GET", url, {
            target: pageContent,
            select: "#page-content",
            swap: "outerHTML show:window:top",
        }).then(() => {
            window.history.pushState({}, "", url);
            updateActiveNav();
        });
        return;
    }

    window.location.href = url;
};

const userInitials = (user) => {
    const source = user?.username || user?.email || "RS";
    const pieces = source
        .split(/[\s._-]+/)
        .filter(Boolean)
        .slice(0, 2);

    return pieces.map((piece) => piece[0].toUpperCase()).join("") || "RS";
};

const updateAuthUI = (user) => {
    const guestLink = document.querySelector("[data-auth-guest-link]");
    const userChip = document.querySelector("[data-auth-user-chip]");
    const userName = document.querySelector("[data-auth-name]");
    const userEmail = document.querySelector("[data-auth-email]");
    const userAvatar = document.querySelector("[data-auth-avatar]");

    if (user) {
        if (guestLink) guestLink.hidden = true;
        if (userChip) userChip.hidden = false;
        if (userName) userName.textContent = user.username;
        if (userEmail) userEmail.textContent = user.email;
        if (userAvatar) userAvatar.textContent = userInitials(user);
        return;
    }

    if (guestLink) guestLink.hidden = false;
    if (userChip) userChip.hidden = true;
};

const fetchAuthUser = async () => {
    const { token } = readStoredAuth();
    if (!token) return null;

    const response = await fetch("/api/users/me", {
        headers: getAuthHeaders(),
    });

    if (!response.ok) {
        clearAuth();
        updateAuthUI(null);
        return null;
    }

    const user = await readJson(response);
    saveAuth({ token, user });
    updateAuthUI(user);
    return user;
};

const syncAuthState = async () => {
    const { user } = readStoredAuth();
    updateAuthUI(user);
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
        visitPage(`/users/${user.user_id}`);
    }, 500);
};

const handleLogin = async (form) => {
    const formData = new FormData(form);
    const email = String(formData.get("email") || "").trim();
    const payload = {
        username: email,
        password: formData.get("password"),
    };

    const tokenResponse = await submitFormUrlEncoded("/api/users/token", payload);
    const token = tokenResponse.access_token;
    const user = {
        username: email.split("@")[0] || email,
        email,
    };

    saveAuth({ token, user });
    updateAuthUI(user);
    window.setTimeout(() => {
        visitPage("/");
    }, 150);
};

const handleLogout = async (form) => {
    clearAuth();
    updateAuthUI(null);
    window.setTimeout(() => {
        visitPage("/");
    }, 150);
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
        visitPage(`/users/${book.user_id}/books`);
    }, 500);
};

const handleUpdateUser = async (form) => {
    const formData = new FormData(form);
    const userId = form.dataset.userId;
    const payload = {
        username: formData.get("username"),
        email: formData.get("email"),
        image_file: formData.get("image_file") || null,
    };
    const password = formData.get("password");

    if (password) {
        payload.password = password;
    }

    const user = await updateJson(`/api/users/${userId}`, payload);
    showMessage(form, "success", "User updated.");
    window.setTimeout(() => {
        visitPage(`/users/${user.user_id}`);
    }, 500);
};

const handleUpdateBook = async (form) => {
    const formData = new FormData(form);
    const bookId = form.dataset.bookId;
    const genreIds = formData.getAll("genre_ids").map((value) => Number(value));

    if (!genreIds.length) {
        throw new Error("Choose at least one genre.");
    }

    const payload = {
        title: formData.get("title"),
        author_id: Number(formData.get("author_id")),
        user_id: Number(formData.get("user_id")),
        published_year: Number(formData.get("published_year")),
        status: formData.get("status"),
        rating: Number(formData.get("rating")),
        genre_ids: genreIds,
    };

    const book = await updateJson(`/api/books/${bookId}`, payload);
    showMessage(form, "success", "Book updated.");
    window.setTimeout(() => {
        visitPage(`/users/${book.user_id}/books`);
    }, 500);
};

document.body.addEventListener("submit", async (event) => {
    const form = event.target.closest("[data-api-form]");
    if (!form) return;

    event.preventDefault();
    const submitButton = form.querySelector("button[type='submit']");
    const formType = form.dataset.apiForm;

    if (submitButton) submitButton.disabled = true;

    try {
        if (formType === "login") {
            await handleLogin(form);
        }

        if (formType === "logout") {
            await handleLogout(form);
        }

        if (formType === "create-user") {
            await handleCreateUser(form);
        }

        if (formType === "add-book") {
            await handleAddBook(form);
        }

        if (formType === "update-user") {
            await handleUpdateUser(form);
        }

        if (formType === "update-book") {
            await handleUpdateBook(form);
        }

        if (window.htmx) {
            window.htmx.trigger(document.body, "library:changed");
        }
    } catch (error) {
        showMessage(form, "error", error.message);
    } finally {
        if (submitButton) submitButton.disabled = false;
    }
});

document.body.addEventListener("click", async (event) => {
    const authLogout = event.target.closest("[data-auth-logout]");
    if (authLogout) {
        event.preventDefault();
        clearAuth();
        updateAuthUI(null);
        visitPage("/");
        return;
    }

    const button = event.target.closest("[data-api-delete]");
    if (!button) return;

    const resource = button.dataset.apiDelete;
    const id = button.dataset.id;
    const redirect = button.dataset.redirect || "/";
    const confirmed = window.confirm(`Delete this ${resource}?`);

    if (!confirmed) return;

    button.disabled = true;

    try {
        await deleteJson(`/api/${resource}s/${id}`);
        visitPage(redirect);
    } catch (error) {
        window.alert(error.message);
        button.disabled = false;
    }
});

document.body.addEventListener("htmx:pushedIntoHistory", updateActiveNav);
document.body.addEventListener("htmx:historyRestore", updateActiveNav);
window.addEventListener("popstate", updateActiveNav);
updateActiveNav();
syncAuthState();
