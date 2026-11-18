const LOCAL_PHONE_DIGITS = 9

function kasa1() {
    return {
        ...inventoryMixin(),
        ...queueMixin(),
        ...wsSyncMixin(),

        // --- STATE AND VARIABLES ---
        skipPhone: localStorage.getItem('kasa1_skipPhone') === 'true',
        formattedPhone: localStorage.getItem('kasa1_skipPhone') === 'true' ? "" : "+380 ",
        rawDigits: "",
        shoeSizes: [],
        durationMinutes: 60,
        availableDurations: [30, 45, 60, 90, 120],
        comment: "",
        createdTicket: null,
        inventoryError: false,
        activeTab: 'figure',

        // --- COMPUTED PROPERTIES ---
        get canSubmit() {
            const hasPhoneOrSkipped = this.skipPhone || this.rawDigits.length >= LOCAL_PHONE_DIGITS;
            return this.shoeSizes.length > 0 && hasPhoneOrSkipped;
        },

        get filteredInventory() {
            const filtered = {}
            for (const [size, data] of Object.entries(this.inventory)) {
                const lower = String(size).toLowerCase()
                const isHockey = lower.includes('хок') || lower.includes('hok')
                if (this.activeTab === 'hockey' && isHockey) {filtered[size] = data}
                else if (this.activeTab === 'figure' && !isHockey) {filtered[size] = data}
            }
            return filtered
        },

        // --- INVENTORY MANAGEMENT ---
        async retryInventory() {
            this.inventoryError = false
            await this.fetchInventory()
        },

        // --- SIZE SELECTION ---
        addSize(size) {
            const total = this.inventory[size]?.total || 999
            const currentSelected = this.getSizeCount(size)
            if (currentSelected < total) { this.shoeSizes.push(size) }
        },
        removeSize(size) {
            const index = this.shoeSizes.lastIndexOf(size)
            if (index !== -1) { this.shoeSizes.splice(index, 1)}
        },
        getSizeCount(size) {return this.shoeSizes.filter(s => s === size).length},
        clearSizes() {this.shoeSizes = []},

        // --- PHONE MASKS ---
        formatPhoneInput() {
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
        toggleSkipPhone() {
            localStorage.setItem('kasa1_skipPhone', this.skipPhone);
            if (this.skipPhone) {this.formattedPhone = ""; this.rawDigits = ""} else {this.formattedPhone = "+380 "}
        },

        // --- FORM SUBMISSION ---
        resetForm() {
            // Не скидаємо skipPhone тут, щоб він залишався увімкненим/вимкненим за вибором касира
            this.formattedPhone = this.skipPhone ? "" : "+380 "
            this.rawDigits = ""
            this.shoeSizes = []
            this.durationMinutes = 60
            this.comment = ""
        },

        async submitForm() {
            if (!this.canSubmit) return
            const fullPhone = this.skipPhone ? null : ("+380" + this.rawDigits)
            const displayPhone = this.skipPhone ? "Без телефону" : this.formattedPhone
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
                if (!response.ok) {
                    const errorBody = await response.text()
                    console.error("Помилка сервера:", response.status, errorBody)
                    return
                }
                this.createdTicket = await response.json()
                this.createdTicket.phone = displayPhone
                this.resetForm()
            } catch (e) {console.error("Помилка створення квитка:", e)}
        },

        // --- LIFECYCLE ---
        async init() {
            this.initInventory()
            if (typeof this.fetchQueue === "function") await this.fetchQueue()
            this.initWebSocket()
        }
    }
}
