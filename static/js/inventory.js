function inventory(config = {}) {
    return {
        inventory: {},
        isAdmin: config.isAdmin || false,
        wsConnected: false,
        now: Math.floor(Date.now() / 1000),
        newSize: '',
        newTotal: 1,

        get wsStatus() {return getWsStatus(this.wsConnected)},

        async init() {
            await this.fetchInventory()

            createQueueWebSocket({
                onOpen: () => {this.wsConnected = true},
                onMessage: () => {void this.fetchInventory()},
                onClose: () => {this.wsConnected = false}
            })

            setInterval(() => {this.now = Math.floor(Date.now() / 1000)}, 1000)
            setInterval(() => {if (!document.hidden) {void this.fetchInventory()}}, 5000)
        },

        async fetchInventory() {
            try {
                const res = await fetch("/api/inventory")
                if (res.ok) {
                    const rawData = await res.json()

                    // Сортуємо ключі природним шляхом (Natural Sort: 38, 38_hok, 39, 40...)
                    const sortedKeys = Object.keys(rawData).sort((a, b) =>
                        a.localeCompare(b, undefined, {numeric: true, sensitivity: 'base'})
                    )

                    // Перебудовуємо об'єкт у потрібному порядку
                    const sortedInventory = {}
                    sortedKeys.forEach(key => {sortedInventory[key] = rawData[key]})
                    this.inventory = sortedInventory
                }
            } catch (e) {console.error("Помилка завантаження залишків:", e)}
        },

        async addSize() {
            if (!this.newSize) return
            try {
                const res = await fetch("/api/inventory", {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        size: this.newSize,
                        total_stock: Number(this.newTotal),
                        maintenance_count: 0
                    })
                })
                if (res.ok) {
                    this.newSize = ''
                    this.newTotal = 1
                    await this.fetchInventory()
                } else {
                    const err = await res.json()
                    alert(err.detail || "Помилка при додаванні розміру")
                }
            } catch (e) {
                console.error("Помилка додавання:", e)
            }
        },

        async updateStock(size, totalStock, maintenanceCount) {
            if (totalStock < 0 || (maintenanceCount !== undefined && maintenanceCount < 0)) return
            try {
                const payload = {size: size, total_stock: totalStock}
                if (maintenanceCount !== undefined) {payload.maintenance_count = maintenanceCount}

                const res = await fetch("/api/inventory", {
                    method: 'PATCH',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                })
                if (res.ok) {await this.fetchInventory()}
            } catch (e) {console.error("Помилка оновлення:", e)}
        },

        async deleteSize(size) {
            if (!confirm(`Видалити розмір ${size} з бази?`)) return
            try {
                const res = await fetch(`/api/inventory?size=${encodeURIComponent(size)}`, {method: 'DELETE'})
                if (res.ok) {await this.fetchInventory()}
            } catch (e) {console.error("Помилка видалення:", e)}
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