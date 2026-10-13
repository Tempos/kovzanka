const LOCAL_PHONE_DIGITS = 9

function kasa1() {
    return {
        formattedPhone: "+380 ",
        rawDigits: "",
        shoeSizes: [],
        durationMinutes: 60, // Default session duration
        availableDurations: [30, 45, 60, 90, 120],
        comment: "",
        createdTicket: null,
        inventory: {},

        get canSubmit() {return this.shoeSizes.length > 0 && this.rawDigits.length >= LOCAL_PHONE_DIGITS},

        async fetchInventory() {
            try {
                const res = await fetch('/api/inventory')
                if (res.ok) { this.inventory = await res.json() }
            } catch (e) { console.error("Помилка оновлення залишків ковзанів:", e) }
        },

        async fetchQueue() {
            try {
                const res = await fetch('/api/queue')
                if (res.ok) { this.queue = await res.json() }
            } catch (e) { console.error("Помилка завантаження черги:", e) }
        },

        // --- МЕТОДИ КЕРУВАННЯ РОЗМІРАМИ (ПКМ / ЛКМ) ---
        addSize(size) {this.shoeSizes.push(size)},
        removeSize(size) {
            const index = this.shoeSizes.lastIndexOf(size);
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
            const parts = [
                digits.substring(0, 2),
                digits.substring(2, 5),
                digits.substring(5, 7),
                digits.substring(7, 9)
            ].filter(Boolean)
            return "+380 " + parts.join(" ")
        },

        statusLink(ticket) { return "/status?ticket=" + ticket.ticket_number },

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
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
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
            await Promise.all([this.fetchQueue(), this.fetchInventory()]);
            createQueueWebSocket({
                onOpen: () => { this.wsConnected = true; },
                onMessage: () => { void this.fetchQueue(); void this.fetchInventory(); },
                onClose: () => { this.wsConnected = false; }
            });
        }
    }
}
