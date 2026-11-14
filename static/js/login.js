document.addEventListener("alpine:init", () => {
    Alpine.data("loginForm", () => ({
        // --- STATE ---
        pin: "",
        errorMessage: "",

        // --- ACTIONS ---
        async submitLogin() {
            this.errorMessage = ""
            const urlParams = new URLSearchParams(window.location.search)
            const roleParam = urlParams.get("role")
            const nextParam = urlParams.get("next") || "/"

            try {
                const res = await fetch("/api/login", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({pin: this.pin, role: roleParam})
                })

                if (res.ok) {window.location.href = nextParam}
                else {
                    const errData = await res.json()
                    this.errorMessage = errData.detail || "Невірний ПІН-код"
                    this.pin = ""
                }
            } catch (e) {this.errorMessage = "Помилка мережі. Спробуйте пізніше."}
        }
    }))
})