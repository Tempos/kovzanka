function inventory(config = {}) {
    return {
        ...inventoryMixin(),
        ...wsSyncMixin(),
        ...scrollTopMixin(),

        // --- STATE AND VARIABLES ---
        isAdmin: config.isAdmin || false,
        wsConnected: false,
        newSize: "",
        expandRange: false,
        newCategory: "figure",
        newTotal: 1,
        sortColumn: "size",
        sortAsc: true,

        get wsStatus() { return getWsStatus(this.wsConnected) },

        // --- COMPUTED PROPERTIES ---
        get sortedInventory() {
            const entries = Object.entries(this.inventory).map(([size, data]) => ({size, ...data}))

            return entries.sort((a, b) => {
                let valA, valB

                if (this.sortColumn === "size") {
                    valA = a.size
                    valB = b.size
                    const cmp = valA.localeCompare(valB, undefined, {numeric: true, sensitivity: "base"})
                    return this.sortAsc ? cmp : -cmp
                }

                if (this.sortColumn === "target_timestamp") {
                    valA = a.target_timestamp || 9999999999
                    valB = b.target_timestamp || 9999999999
                } else {
                    valA = a[this.sortColumn] ?? 0
                    valB = b[this.sortColumn] ?? 0
                }

                if (valA < valB) return this.sortAsc ? -1 : 1
                if (valA > valB) return this.sortAsc ? 1 : -1
                return 0
            })
        },

        sortBy(column) {
            if (this.sortColumn === column) {this.sortAsc = !this.sortAsc} else {
                this.sortColumn = column
                this.sortAsc = true
            }
        },

        // --- API ACTIONS ---
        async addSize() {
            if (!this.newSize.trim()) return

            const raw = this.newSize.trim()

            try {
                const res = await fetch("/api/inventory", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        size: raw,
                        category: this.newCategory,
                        total_stock: Number(this.newTotal),
                        maintenance_count: 0,
                        expand_range: Boolean(this.expandRange)
                    })
                })
                if (res.ok) {
                    this.newSize = ""
                    this.newCategory = "figure"
                    this.expandRange = false
                    this.newTotal = 1
                    await this.fetchInventory()
                } else {
                    const err = await res.json()
                    alert(err.detail || "Помилка при додаванні розміру")
                }
            } catch (e) {console.error("Помилка додавання:", e)}
        },

        async updateStock(size, totalStock, maintenanceCount) {
            if (totalStock < 0) return
            if (maintenanceCount !== undefined && (maintenanceCount < 0 || maintenanceCount > totalStock)) {
                alert("Кількість ковзанів на ремонті не може перевищувати загальну кількість!")
                return
            }

            try {
                const payload = {size: size, total_stock: totalStock}
                if (maintenanceCount !== undefined) {payload.maintenance_count = maintenanceCount}

                const res = await fetch("/api/inventory", {
                    method: "PATCH",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify(payload)
                })

                if (res.ok) {await this.fetchInventory()} else {
                    const err = await res.json()
                    alert(err.detail || "Помилка оновлення кількості")
                }
            } catch (e) {console.error("Помилка оновлення:", e)}
        },

        async deleteSize(size) {
            if (!confirm(`Видалити розмір ${size} з бази?`)) return
            try {
                const res = await fetch(`/api/inventory?size=${encodeURIComponent(size)}`, {method: "DELETE"})
                if (res.ok) {await this.fetchInventory()}
            } catch (e) {console.error("Помилка видалення:", e)}
        },

        // --- LIFECYCLE ---
        async init() {
            this.initScrollTop()
            this.initInventory()
            this.initWebSocket()
        }
    }
}
