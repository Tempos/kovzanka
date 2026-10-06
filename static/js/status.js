function statusApp() {
    return {
        ticketNumber: "", inputTicket: "", data: {}, pollInterval: null,

        // --- API ACTIONS ---
        searchTicket() {
            if (this.inputTicket.toString().trim()) {
                window.location.search = `?ticket=${this.inputTicket.toString().trim()}`
            }
        },

        resetTicket() {
            if (this.pollInterval) clearInterval(this.pollInterval)
            window.location.href = window.location.pathname
        },

        async fetchStatus() {
            if (!this.ticketNumber) return
            try {
                const res = await fetch(`/api/public/status/ticket/${this.ticketNumber}`)
                if (res.ok) {
                    this.data = await res.json()
                } else {
                    this.data = {status: "НЕ ЗНАЙДЕНО"}
                }
            } catch (e) {
                console.error("Помилка завантаження статусу:", e)
            }
        },

        init() {
            const urlParams = new URLSearchParams(window.location.search)
            this.ticketNumber = urlParams.get("ticket") || ""
            if (!this.ticketNumber) return

            this.fetchStatus()
            this.pollInterval = setInterval(() => this.fetchStatus(), 5000)

            createQueueWebSocket({
                onMessage: () => this.fetchStatus(), onOpen: () => this.fetchStatus()
            })

            document.addEventListener("visibilitychange", () => {
                if (document.visibilityState === "visible") this.fetchStatus()
            })
            window.addEventListener("pageshow", (event) => {
                if (event.persisted) this.fetchStatus()
            })
        }
    }
}