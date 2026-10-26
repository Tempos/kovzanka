document.addEventListener("alpine:init", () => {
    Alpine.data("loginForm", () => ({
        pin: "",
        errorMessage: "",
        async submitLogin() {
            this.errorMessage = ""
            try {
                const res = await fetch("/api/login", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({pin: this.pin})
                })

                if (res.ok) {window.location.href = new URLSearchParams(window.location.search).get("next") || "/"
                } else {
                    const errData = await res.json()
                    this.errorMessage = errData.detail || "Невірний ПІН-код"
                    this.pin = ""
                }
            } catch (e) {this.errorMessage = "Помилка мережі. Спробуйте пізніше."}
        }
    }))
})
