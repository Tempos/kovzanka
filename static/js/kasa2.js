function kasa2App() {
    return {
        queue: [], wsConnected: false, socket: null, fetchTimer: null,
        // --- FORMATTERS ---
        formatPhone, formatTime,

        // --- API ACTIONS ---
        async fetchQueue() {
            try {
                const response = await fetch("/api/queue")
                if (response.ok) {this.queue = await response.json()}
            } catch (e) {console.error("Помилка завантаження черги:", e)}
        },

        get wsStatus() { return getWsStatus(this.wsConnected) },

        async changeStatus(itemId, newStatus) {
            const item = this.queue.find(i => i.id === itemId)
            if (item) item.status = newStatus

            try {
                const response = await fetch(`/api/queue/${itemId}/status?status=${encodeURIComponent(newStatus)}`, {
                    method: "PATCH", headers: {"Content-Type": "application/json"}
                })
                if (!response.ok) await this.fetchQueue()
            } catch (e) {
                console.error("Помилка зміни статусу:", e)
                await this.fetchQueue()
            }
        },

        async extendSession(itemId, minutes = 15) {
            const item = this.queue.find(i => i.id === itemId)
            if (!item) return

            try { // 2. Background API call
                const response = await fetch(`/api/queue/${itemId}/extend`, {
                    method: "PATCH", headers: {"Content-Type": "application/json"}, body: JSON.stringify({minutes})
                })
                if (!response.ok) await this.fetchQueue()
            } catch (e) {
                console.error("Помилка продовження сеансу:", e)
                await this.fetchQueue()
            }
        },

        getOverdueMinutes(sessionEndIso) {
            if (!sessionEndIso) return 0

            const endTime = new Date(sessionEndIso).getTime()
            const now = Date.now()
            const diffMinutes = Math.floor((now - endTime) / (1000 * 60))
            return diffMinutes > 0 ? diffMinutes : 0
        },

        async init() {
            await this.fetchQueue()
            setInterval(() => {this.queue = [...this.queue]}, 30000)

            createQueueWebSocket({
                onOpen: () => {
                    this.wsConnected = true
                    void this.fetchQueue()
                }, onMessage: () => {
                    clearTimeout(this.fetchTimer)
                    this.fetchTimer = setTimeout(() => { void this.fetchQueue() }, 500)
                }, onClose: () => {this.wsConnected = false}
            })
        }
    }
}