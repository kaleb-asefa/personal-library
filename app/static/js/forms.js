const SESSION_KEY = "personal-library-token";
let sessionUser = null;

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

const getSessionToken = () => window.localStorage.getItem(SESSION_KEY);

const getAuthHeaders = () => {
    const token = getSessionToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
};

const submitJson = async (url, payload) => {
    const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify(payload),
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
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
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
    const response = await fetch(url, { method: "DELETE", headers: getAuthHeaders() });

    if (!response.ok) {
        const data = await readJson(response);
        const message = data.message || data.detail || "Something went wrong.";
        throw new Error(typeof message === "string" ? message : "Delete failed.");
    }
};

const getActiveNavHref = (pathname) => {
    if (pathname === "/users/new") return "/users/new";
    if (pathname === "/books/new") return "/books/new";
    if (pathname === "/login") return "/login";
    if (pathname === "/logout") return "/logout";
    if (sessionUser && pathname === `/users/${sessionUser.user_id}`) return `/users/${sessionUser.user_id}`;
    if (sessionUser && (pathname === `/users/${sessionUser.user_id}/books` || pathname.startsWith("/books/"))) {
        return `/users/${sessionUser.user_id}/books`;
    }
    return pathname;
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

const login = async (email, password) => {
    const body = new URLSearchParams({ username: email, password });
    const response = await fetch("/api/users/token", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
    });
    const data = await readJson(response);

    if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Unable to sign in.");
    }

    window.localStorage.setItem(SESSION_KEY, data.access_token);
};

const loadSessionUser = async () => {
    const token = getSessionToken();
    if (!token) return null;

    const response = await fetch("/api/users/me", { headers: getAuthHeaders() });
    if (!response.ok) {
        window.localStorage.removeItem(SESSION_KEY);
        return null;
    }

    return readJson(response);
};

const applySessionToPage = () => {
    document.querySelectorAll("[data-auth-only]").forEach((element) => {
        element.hidden = !sessionUser;
    });
    document.querySelectorAll("[data-guest-only]").forEach((element) => {
        element.hidden = Boolean(sessionUser);
    });

    if (sessionUser) {
        const sessionLinks = {
            shelf: `/users/${sessionUser.user_id}/books`,
            profile: `/users/${sessionUser.user_id}`,
        };
        document.querySelectorAll("[data-session-link]").forEach((link) => {
            link.href = sessionLinks[link.dataset.sessionLink];
        });
        document.querySelectorAll("[data-session-username]").forEach((element) => {
            element.textContent = sessionUser.username;
        });
    }

    updateActiveNav();
};

const enforcePageAccess = () => {
    const protectedView = document.querySelector("[data-auth-required]");
    const ownerView = document.querySelector("[data-owner-id]");

    if (protectedView && !sessionUser) {
        window.location.replace(`/login?next=${encodeURIComponent(window.location.pathname)}`);
        return;
    }

    if (ownerView && sessionUser && Number(ownerView.dataset.ownerId) !== sessionUser.user_id) {
        window.location.replace(`/users/${sessionUser.user_id}/books`);
        return;
    }

    if (window.location.pathname === "/" && sessionUser) {
        window.location.replace(`/users/${sessionUser.user_id}/books`);
        return;
    }

    if (sessionUser && ["/login", "/users/new"].includes(window.location.pathname)) {
        window.location.replace(`/users/${sessionUser.user_id}/books`);
    }
};

const hydrateSession = async () => {
    sessionUser = await loadSessionUser();
    applySessionToPage();
    enforcePageAccess();
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

const handleCreateUser = async (form) => {
    const formData = new FormData(form);
    const payload = {
        username: formData.get("username"),
        email: formData.get("email"),
        password: formData.get("password") || null,
    };

    await submitJson("/api/users", payload);
    await login(payload.email, payload.password);
    sessionUser = await loadSessionUser();
    showMessage(form, "success", "Account created. Opening your shelf...");
    window.setTimeout(() => {
        visitPage(`/users/${sessionUser.user_id}/books`);
    }, 500);
};

const handleLogin = async (form) => {
    const formData = new FormData(form);
    await login(formData.get("email"), formData.get("password"));
    sessionUser = await loadSessionUser();
    showMessage(form, "success", "Signed in. Opening your shelf...");

    const nextUrl = new URLSearchParams(window.location.search).get("next");
    const destination = nextUrl && nextUrl.startsWith("/") ? nextUrl : `/users/${sessionUser.user_id}/books`;
    window.setTimeout(() => visitPage(destination), 350);
};

const handleAddBook = async (form) => {
    const formData = new FormData(form);
    const genreNames = formData.getAll("genre_names");

    if (!genreNames.length) {
        throw new Error("Choose at least one genre.");
    }

    const payload = {
        title: formData.get("title"),
        author_name: formData.get("author_name"),
        published_year: Number(formData.get("published_year")),
        user_id: sessionUser.user_id,
        genre_names: genreNames,
    };

    const book = await submitJson("/api/books", payload);
    showMessage(form, "success", "Book added.");
    window.setTimeout(() => {
        visitPage(`/users/${sessionUser.user_id}/books`);
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
        user_id: sessionUser.user_id,
        published_year: Number(formData.get("published_year")),
        status: formData.get("status"),
        rating: Number(formData.get("rating")),
        genre_ids: genreIds,
    };

    const book = await updateJson(`/api/books/${bookId}`, payload);
    showMessage(form, "success", "Book updated.");
    window.setTimeout(() => {
        visitPage(`/users/${sessionUser.user_id}/books`);
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
        if (formType === "create-user") {
            await handleCreateUser(form);
        }

        if (formType === "login") {
            await handleLogin(form);
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
    const logoutButton = event.target.closest("[data-logout]");
    if (logoutButton) {
        window.localStorage.removeItem(SESSION_KEY);
        sessionUser = null;
        window.location.replace("/login");
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
document.body.addEventListener("htmx:afterSwap", () => {
    applySessionToPage();
    enforcePageAccess();
});
document.body.addEventListener("htmx:historyRestore", () => {
    applySessionToPage();
    enforcePageAccess();
});
window.addEventListener("popstate", updateActiveNav);
hydrateSession();
