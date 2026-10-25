function inventory() {
    return {
        inventory: {},
        wsConnected: false,
        now: Math.floor(Date.now() / 1000),

        get wsStatus() { return getWsStatus(this.wsConnected) },

        async init() {
            await this.fetchInventory()

            createQueueWebSocket({
                onOpen: () => { this.wsConnected = true },
                onMessage: () => { void this.fetchInventory() },
                onClose: () => { this.wsConnected = false }
            })

            // Local 1-second ticker for smooth countdown UI updates
            setInterval(() => { this.now = Math.floor(Date.now() / 1000) }, 1000)

            // Background sync every 5 seconds
            setInterval(() => { if (!document.hidden) { void this.fetchInventory() } }, 5000)
        },

        async fetchInventory() {
            try {
                const res = await fetch("/api/inventory")
                if (res.ok) { this.inventory = await res.json() }
            } catch (e) {console.error("Помилка завантаження залишків:", e)}
        },

        formatCountdown(targetTimestamp, currentTime) {
            if (!targetTimestamp) return "—"
            const diff = targetTimestamp - currentTime
            if (diff <= 0) return "0 с"

            const mins = Math.floor(diff / 60)
            const secs = diff % 60
            return mins > 0 ? `${mins} хв ${String(secs).padStart(2, "0")} с` : `${secs} с`
        }
    }
}