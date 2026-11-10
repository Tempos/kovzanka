function kasa2App() {
    return {
        ...inventoryMixin(),
        ...queueMixin(),
        ...wsSyncMixin(),

        showInventoryModal: false,
        inventory: {},
        fetchTimer: null,
        now: Date.now(), // 1. Реактивна змінна для поточного часу

        // --- FORMATTERS ---
        formatPhone, formatTime,

        async fetchInventory() {
            try {
                const res = await fetch("/api/inventory")
                if (res.ok) {
                    const rawData = await res.json()

                    // Природне сортування ключів (числа на початок, потім текст)
                    const sortedKeys = Object.keys(rawData).sort((a, b) =>
                        a.localeCompare(b, undefined, {numeric: true, sensitivity: 'base'})
                    )

                    const sortedInventory = {}
                    sortedKeys.forEach(key => {sortedInventory[key] = rawData[key]})
                    this.inventory = sortedInventory
                }
            } catch (e) {console.error("Помилка завантаження залишків у Касі 2:", e)}
        },

        // --- API ACTIONS ---
        get wsStatus() {return getWsStatus(this.wsConnected)},

        async changeStatus(itemId, newStatus) {
            const item = this.queue.find(i => i.id === itemId)
            if (!item) return

            const currentStatus = item.status
            item.status = newStatus // Optimistic UI update

            try {
                const response = await fetch(
                    `/api/queue/${itemId}/status?status=${encodeURIComponent(newStatus)}&expected_status=${encodeURIComponent(currentStatus)}`,
                    {method: "PATCH", headers: {"Content-Type": "application/json"}})
                if (!response.ok) {await this.fetchQueue()}
            } catch (e) {
                console.error("Помилка зміни статусу:", e)
                await this.fetchQueue()
            }
        },

        async extendSession(itemId, minutes = 15) {
            const item = this.queue.find(i => i.id === itemId)
            if (!item) return

            try {
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
            const diffMinutes = Math.floor((this.now - endTime) / (1000 * 60))
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
            const diffMs = end.getTime() - this.now
            if (diffMs <= 0) return null
            return this.formatMs(diffMs)
        },

        // Counts up once the session end has passed
        getOverdueTime(sessionEndIso) {
            const end = parseServerDate(sessionEndIso)
            if (!end) return null
            const diffMs = this.now - end.getTime()
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

        // --- QUEUE FILTER GETTERS ---
        get activeQueue() {
            return this.queue.filter(i =>
                ['ЧЕКАЄ', 'ВИКЛИКАЄТЬСЯ', 'ОБСЛУГОВУЄТЬСЯ', 'WAITING', 'CALLING', 'SERVED'].includes(i.status)
            )
        },

        get closedQueue() {
            return this.queue.filter(i =>
                ['ПОВЕРНЕНО', 'СКАСОВАНО', 'RETURNED', 'CANCELLED'].includes(i.status)
            )
        },

        async confirmCancel(itemId) {
            if (window.confirm("Ви дійсно хочете скасувати цей квиток?")) {
                await this.changeStatus(itemId, 'СКАСОВАНО')
            }
        },

        async revertStatus(itemId) {
            console.log("Кнопка відкату натиснута для ID:", itemId) // <-- Debug log
            try {
                const response = await fetch(`/api/queue/${itemId}/revert`, {
                    method: "POST", headers: {"Content-Type": "application/json"}
                })
                if (!response.ok) {
                    const err = await response.text()
                    console.error("Помилка відкату:", err)
                    return
                }
                await this.fetchQueue()
            } catch (e) {console.error("Помилка відкату статусу:", e)}
        },

        async init() {
            this.initInventory()
            if (typeof this.fetchQueue === "function") await this.fetchQueue()
            setInterval(() => {this.now = Date.now()}, 1000)
            this.initWebSocket()
        }
    }
}