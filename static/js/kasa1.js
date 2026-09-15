const LOCAL_PHONE_DIGITS = 9
const MIN_SHOE_SIZE = 26
const MAX_SHOE_SIZE = 48

function kasa1() {
    return {
        formattedPhone: "+380 ",
        rawDigits: "",
        shoeSizes: [],
        durationMinutes: 60, // Default session duration
        availableDurations: [30, 45, 60, 90, 120],
        comment: "",
        createdTicket: null,
        availableSizes: Array.from({length: MAX_SHOE_SIZE - MIN_SHOE_SIZE + 1}, (_, i) => MIN_SHOE_SIZE + i),

        get canSubmit() {return this.shoeSizes.length > 0 && this.rawDigits.length >= LOCAL_PHONE_DIGITS},

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

        addSize(size) { this.shoeSizes.push(size) },
        getSizeCount(size) { return this.shoeSizes.filter(s => s === size).length },
        removeSizeAtIndex(index) { this.shoeSizes.splice(index, 1) },
        clearSizes() { this.shoeSizes = [] },
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
        }
    }
}