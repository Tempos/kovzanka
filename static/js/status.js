function statusApp() {
    return {
        ...queueMixin(),
        ...wsSyncMixin(),

        // --- STATE ---
        ticketNumber: "",
        inputTicket: "",
        apiData: {},
        now: Date.now(),

        // --- COMPUTED PROPERTIES ---
        get data() {
            if (!this.ticketNumber) return {}
            const foundInQueue = this.queue.find(item => String(item.ticket_number) === String(this.ticketNumber)) || {}

            return {
                ...foundInQueue,
                ...this.apiData,
                position_in_queue: this.apiData.position_in_queue !== undefined ? this.apiData.position_in_queue : foundInQueue.position_in_queue,
                estimated_wait_minutes: this.apiData.estimated_wait_minutes !== undefined ? this.apiData.estimated_wait_minutes : foundInQueue.estimated_wait_minutes,
                session_end: this.apiData.session_end || foundInQueue.session_end
            }
        },

        // --- ACTIONS & NAVIGATION ---
        searchTicket() {
            const ticketNum = parseInt(this.inputTicket)
            if (!isNaN(ticketNum) && ticketNum >= 101) { window.location.search = `?ticket=${ticketNum}` }
        },

        loadTicket(num) {
            if (num < 101) return
            window.location.search = `?ticket=${num}`
        },

        resetTicket() {window.location.href = window.location.pathname},

        async fetchTicketStatus() {
            if (!this.ticketNumber) return
            await this.fetchQueue()
            try {
                const res = await fetch(`/api/public/status/ticket/${this.ticketNumber}`)
                if (res.ok) {this.apiData = await res.json()}
                else if (!this.apiData.status) {this.apiData = {status: "НЕ ЗНАЙДЕНО"}}
            } catch (e) {console.error("Помилка завантаження статусу:", e)}
        },

        // --- LIFECYCLE ---
        init() {
            const urlParams = new URLSearchParams(window.location.search)
            this.ticketNumber = urlParams.get("ticket") || ""
            if (!this.ticketNumber) return

            this.fetchTicketStatus()
            setInterval(() => { this.now = Date.now() }, 1000)

            this.initWebSocket()

            document.addEventListener("visibilitychange", () => {
                if (document.visibilityState === "visible") this.fetchTicketStatus()
            })
            window.addEventListener("pageshow", (event) => {
                if (event.persisted) this.fetchTicketStatus()
            })
        }
    }
}
