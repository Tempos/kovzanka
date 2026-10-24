const LOCAL_PHONE_DIGITS = 9

function kasa1() {
    return {
        formattedPhone: "+380 ",
        rawDigits: "",
        shoeSizes: [],
        durationMinutes: 60,
        availableDurations: [30, 45, 60, 90, 120],
        comment: "",
        createdTicket: null,
        inventory: {},
        inventoryRequestId: 0,
        inventoryError: false,
        showInventoryModal: false,
        queue: [],
        wsConnected: false,

        // --- ОБЧИСЛЮВАННІ ВЛАСТИВОСТІ ---
        get canSubmit() {return this.shoeSizes.length > 0 && this.rawDigits.length >= LOCAL_PHONE_DIGITS},

        // --- ІНВЕНТАР ТА ЗАЛИШКИ ---
        async fetchInventory() {
            const requestId = ++this.inventoryRequestId
            try {
                const res = await fetch("/api/inventory")
                if (res.ok) {
                    const data = await res.json()
                    if (requestId === this.inventoryRequestId) {
                        this.inventory = data
                        this.inventoryError = false // Clear error on success
                    }
                // Mark error on bad response
                } else if (requestId === this.inventoryRequestId) {this.inventoryError = true}
            } catch (e) {
                console.error("Помилка оновлення залишків ковзанів:", e)
                // Mark error on network catch
                if (requestId === this.inventoryRequestId) {this.inventoryError = true}
            }
        },
        async retryInventory() {
            this.inventoryError = false
            await this.fetchInventory()
        },

        // --- УПРАВЛІННЯ ЧЕРГОЮ ---
        async fetchQueue() {
            try {
                const res = await fetch("/api/queue")
                if (res.ok) { this.queue = await res.json() }
            } catch (e) { console.error("Помилка завантаження черги:", e) }
        },

        // --- МЕТОДИ КЕРУВАННЯ РОЗМІРАМИ (ПКМ / ЛКМ) ---
        addSize(size) {
            const available = this.inventory[size]?.available || 0
            const currentSelected = this.getSizeCount(size)
            if (currentSelected < available) {this.shoeSizes.push(size)}
        },
        removeSize(size) {
            const index = this.shoeSizes.lastIndexOf(size)
            if (index !== -1) { this.shoeSizes.splice(index, 1)}
        },
        getSizeCount(size) {return this.shoeSizes.filter(s => s === size).length},
        clearSizes() {this.shoeSizes = []},

        // --- ОБРОБКА ТЕЛЕФОНУ ТА МАСКИ ---
        formatPhone() {
            const digits = this.extractDigits(this.formattedPhone)
            this.rawDigits = digits
            this.formattedPhone = this.buildPhoneMask(digits)
        },
        extractDigits(value) {
            let digits = value.replace(/\D/g, "")
            if (digits.startsWith("380")) digits = digits.substring(3)
            else if (digits.startsWith("38")) digits = digits.substring(2)
            if (digits.startsWith("0")) digits = digits.substring(1)
            return digits.substring(0, LOCAL_PHONE_DIGITS)
        },
        buildPhoneMask(digits) {
            const parts = [digits.substring(0, 2), digits.substring(2, 5), digits.substring(5, 7), digits.substring(7, 9)].filter(Boolean)
            return "+380 " + parts.join(" ")
        },

        statusLink(ticket) { return "/status?ticket=" + ticket.ticket_number },

        // --- ДІЇ З ФОРМОЮ ТА КВИТКАМИ ---
        resetForm() {
            this.formattedPhone = "+380 "
            this.rawDigits = ""
            this.shoeSizes = []
            this.durationMinutes = 60
            this.comment = ""
        },
        async submitForm() {
            if (!this.canSubmit) return

            const fullPhone = "+380" + this.rawDigits
            const displayPhone = this.formattedPhone

            try {
                const response = await fetch("/api/queue", {
                    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({
                        phone: fullPhone,
                        shoe_sizes: this.shoeSizes,
                        duration_minutes: this.durationMinutes,
                        comment: this.comment || null
                    })
                })
                if (!response.ok) return

                this.createdTicket = await response.json()
                this.createdTicket.phone = displayPhone
                this.resetForm()
            } catch (e) {console.error("Помилка створення квитка:", e)}
        },

        async init() {
            await Promise.all([this.fetchQueue(), this.fetchInventory()])
            createQueueWebSocket({
                onOpen: () => { this.wsConnected = true }, onMessage: () => {
                    void this.fetchQueue()
                    void this.fetchInventory()
                }, onClose: () => { this.wsConnected = false }
            })
        }
    }
}
