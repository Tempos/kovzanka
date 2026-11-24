document.addEventListener("alpine:init", () => {
    Alpine.data("loginForm", () => ({
        username: "",
        password: "",
        errorMessage: "",

        async submitLogin() {
            this.errorMessage = ""
            const cleanUsername = this.username.trim()
            if (!cleanUsername || !this.password) {
                this.errorMessage = "Введіть логін та пароль"
                return
            }

            const urlParams = new URLSearchParams(window.location.search)
            const nextUrl = urlParams.get("next") || ""
            const roleParam = urlParams.get("role") || null

            try {
                const response = await fetch("/api/login", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({username: cleanUsername, password: this.password, role: roleParam})
                })

                if (!response.ok) {
                    const errData = await response.json().catch(() => ({}))
                    throw new Error(errData.detail || "Невірний логін або пароль")
                }

                const data = await response.json()

                if (nextUrl) {window.location.href = nextUrl}
                else if (data.role === "kasa1") {window.location.href = "/kasa1"}
                else if (data.role === "kasa2") {window.location.href = "/kasa2"}
                else {window.location.href = "/staff"}
            } catch (error) {this.errorMessage = error.message || "Помилка авторизації"}
        }
    }))
})