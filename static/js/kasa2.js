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

            const endTime = parseServerDate(sessionEndIso)?.getTime()
            if (!endTime) return 0
            const now = Date.now()
            const diffMinutes = Math.floor((now - endTime) / (1000 * 60))
            return diffMinutes > 0 ? diffMinutes : 0
        },

        // --- LIVE TIMERS ---
        formatMs(diffMs) {
            const totalSeconds = Math.floor(diffMs / 1000)
            const minutes = Math.floor(totalSeconds / 60)
            const seconds = totalSeconds % 60
            return `${minutes}:${seconds.toString().padStart(2, "0")}`
        },

        // Counts down while the session is still active
        getRemainingTime(sessionEndIso) {
            const end = parseServerDate(sessionEndIso)
            if (!end) return null
            const diffMs = end.getTime() - Date.now()
            if (diffMs <= 0) return null
            return this.formatMs(diffMs)
        },

        // Counts up once the session end has passed
        getOverdueTime(sessionEndIso) {
            const end = parseServerDate(sessionEndIso)
            if (!end) return null
            const diffMs = Date.now() - end.getTime()
            if (diffMs <= 0) return null
            return this.formatMs(diffMs)
        },

        // What the top line of the TIME cell should show
        getTimeDisplay(item) {
            const isActive = item.status === "ОБСЛУГОВУЄТЬСЯ" || item.status === "SERVED"
            if (isActive && item.session_end) {
                const remaining = this.getRemainingTime(item.session_end)
                return remaining ?? "00:00"
            }
            return item.duration_minutes ? item.duration_minutes + " хв" : "—"
        },

        async init() {
            await this.fetchQueue()
            // Re-assign every second so Alpine re-evaluates the live timers
            // (getTimeDisplay / getOverdueTime), which aren't stored in reactive state.
            setInterval(() => {this.queue = [...this.queue]}, 1000)

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