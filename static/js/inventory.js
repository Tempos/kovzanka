function inventory() {
    return {
        inventory: {},
        wsConnected: false,

        get wsStatus() {return getWsStatus(this.wsConnected)},

        async init() {
            await this.fetchInventory()

            createQueueWebSocket({
                onOpen: () => {this.wsConnected = true},
                onMessage: () => {void this.fetchInventory()},
                onClose: () => {this.wsConnected = false}
            })

            setInterval(() => { void this.fetchInventory() }, 5000)
        },
        async fetchInventory() {
            try {
                const res = await fetch("/api/inventory")
                if (res.ok) {this.inventory = await res.json()}
            } catch (e) {console.error("Помилка завантаження залишків:", e)}
        }
    }
}