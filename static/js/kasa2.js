function kasa2App() {
    return {
        ...inventoryMixin(),
        ...queueMixin(),
        ...wsSyncMixin(),

        // --- STATE AND VARIABLES ---
        searchQuery: "",
        fetchTimer: null,

        // --- SORTING (за замовчуванням — за номером талона, щоб рядки не стрибали при зміні статусу) ---
        sortColumn: "ticket_number",
        sortAsc: true,

        // --- MODALS (EDIT & CANCEL) ---
        editModal: {
            open: false,
            id: null,
            ticketNumber: "",
            duration: 60,
            availableDurations: [30, 45, 60, 90, 120],
            sizes: [],
            originalSizes: [],
            activeTab: "figure",
            comment: "",
            issueStatus: "", // "" | "warning" | "danger"
            issueNote: ""
        },
        cancelModal: {open: false, id: null, ticketNumber: "", reason: "", error: ""},
        openTechBreakModal() {
            this.techBreakModal = {open: true, username: "", password: "", minutes: 10, customMinutes: "", error: ""}
            this.$nextTick(() => this.$refs.adminPasswordInput?.focus())
        },
        selectTechBreakMinutes(mins) {
            this.techBreakModal.minutes = mins
            this.techBreakModal.customMinutes = ""
            this.techBreakModal.error = ""
        },
        techBreakModal: {open: false, username: "", password: "", minutes: 10, customMinutes: "", error: ""},

        // --- COMPUTED PROPERTIES ---
        get issueFilter() {
            const q = (this.searchQuery || "").trim().toLowerCase()
            if (q === "!") return "warning"
            if (q === "!!") return "danger"
            if (q === "!!!") return "any"
            if (q.length >= 3 && "проблема".startsWith(q)) return "danger"
            if (q.length >= 3 && "увага".startsWith(q)) return "warning"
            return null
        },
        toggleIssueFilter(value) {this.searchQuery = this.searchQuery.trim() === value ? "" : value},
        sortBy(column) {
            if (this.sortColumn === column) {
                this.sortAsc = !this.sortAsc
            } else {
                this.sortColumn = column
                this.sortAsc = true
            }
        },
        sortItems(items) {
            const statusOrder = {"ЧЕКАЄ": 0, "WAITING": 0, "ВИКЛИКАЄТЬСЯ": 1, "CALLING": 1, "ОБСЛУГОВУЄТЬСЯ": 2, "SERVED": 2}
            const keyOf = (item) => {
                switch (this.sortColumn) {
                    case "phone": return item.phone ? String(item.phone).replace(/\D/g, "") : null
                    case "session": return item.session_end ? (parseServerDate(item.session_end)?.getTime() ?? null) : null
                    case "status": return statusOrder[item.status] ?? 99
                    default: return item.ticket_number
                }
            }
            const dir = this.sortAsc ? 1 : -1
            return [...items].sort((a, b) => {
                const ka = keyOf(a), kb = keyOf(b)
                // порожні значення (немає телефону / сеанс ще не розпочато) завжди внизу
                if (ka === null && kb !== null) return 1
                if (kb === null && ka !== null) return -1
                if (ka !== kb && ka !== null) {
                    const cmp = typeof ka === "string" ? ka.localeCompare(kb, undefined, {numeric: true}) : ka - kb
                    if (cmp !== 0) return cmp * dir
                }
                return a.ticket_number - b.ticket_number // однакові значення — завжди за номером
            })
        },
        get activeQueue() {return this.sortItems(this.filteredActiveQueue)},
        get filteredActiveQueue() {
            let items = this.queue.filter(i =>
                ["ЧЕКАЄ", "ВИКЛИКАЄТЬСЯ", "ОБСЛУГОВУЄТЬСЯ", "WAITING", "CALLING", "SERVED"].includes(i.status)
            )

            const flt = this.issueFilter
            if (flt) {
                return items.filter(i => flt === "any" ? (i.issue_status === "warning" || i.issue_status === "danger") : i.issue_status === flt)
            }

            if (!this.searchQuery || this.searchQuery.trim() === "") {return items}

            const q = this.searchQuery.trim().toLowerCase()
            return items.filter(item => {
                if (String(item.ticket_number).includes(q)) return true
                if (item.id && String(item.id).toLowerCase().includes(q)) return true
                if (item.phone && String(item.phone).toLowerCase().includes(q)) return true
                const formattedPh = formatPhone(item.phone)
                if (formattedPh && formattedPh.toLowerCase().includes(q)) return true
                if (item.comment && String(item.comment).toLowerCase().includes(q)) return true
                if (item.shoe_sizes && Array.isArray(item.shoe_sizes)) {
                    if (item.shoe_sizes.some(sz => String(sz).toLowerCase().includes(q))) return true
                }
                return false
            })
        },
        get closedQueue() {
            let items = this.queue.filter(i =>
                ["ПОВЕРНЕНО", "СКАСОВАНО", "RETURNED", "CANCELLED"].includes(i.status)
            )

            if (this.issueFilter) return [] // фільтр проблемних стосується лише активних квитків

            if (!this.searchQuery || this.searchQuery.trim() === "") {return items}

            const q = this.searchQuery.trim().toLowerCase()
            return items.filter(item => {
                if (String(item.ticket_number).includes(q)) return true
                if (item.id && String(item.id).toLowerCase().includes(q)) return true
                if (item.phone && String(item.phone).toLowerCase().includes(q)) return true
                const formattedPh = formatPhone(item.phone)
                if (formattedPh && formattedPh.toLowerCase().includes(q)) return true
                if (item.comment && String(item.comment).toLowerCase().includes(q)) return true
                if (item.shoe_sizes && Array.isArray(item.shoe_sizes)) {
                    if (item.shoe_sizes.some(sz => String(sz).toLowerCase().includes(q))) return true
                }
                return false
            })
        },
        get filteredEditInventory() {
            const filtered = {}
            for (const [size, data] of Object.entries(this.inventory)) {
                const lower = String(size).toLowerCase()
                const isHockey = lower.includes("хок") || lower.includes("hok")

                if (this.editModal.activeTab === "hockey" && isHockey) {filtered[size] = data} else if (this.editModal.activeTab === "figure" && !isHockey) {filtered[size] = data}
            }
            return filtered
        },
        // Лічильники рахуємо лише по активних квитках (закриті/скасовані не потребують уваги)
        get issueTickets() {
            return this.queue.filter(i =>
                ["ЧЕКАЄ", "ВИКЛИКАЄТЬСЯ", "ОБСЛУГОВУЄТЬСЯ", "WAITING", "CALLING", "SERVED"].includes(i.status)
                && (i.issue_status === "warning" || i.issue_status === "danger")
            )
        },
        get warningTicketsCount() {return this.issueTickets.filter(i => i.issue_status === "warning").length},
        get dangerTicketsCount() {return this.issueTickets.filter(i => i.issue_status === "danger").length},
        get problemTicketsCount() {return this.issueTickets.length},
        get wsStatus() {return getWsStatus(this.wsConnected)},

        // --- TECH BREAK ---
        onCustomTechBreakInput() {
            const parsed = parseInt(this.techBreakModal.customMinutes, 10)
            if (!Number.isNaN(parsed) && parsed > 0) {this.techBreakModal.minutes = parsed}
            this.techBreakModal.error = ""
        },

        get effectiveTechBreakMinutes() {
            const custom = parseInt(this.techBreakModal.customMinutes, 10)
            if (this.techBreakModal.customMinutes !== "" && !Number.isNaN(custom) && custom > 0) {return custom}
            return this.techBreakModal.minutes || 10
        },

        async submitTechBreak() {
            const cleanUsername = (this.techBreakModal.username || "").trim()
            const mins = this.effectiveTechBreakMinutes
            if (!cleanUsername || !this.techBreakModal.password || !mins || mins <= 0) {
                this.techBreakModal.error = "Введіть логін, пароль та коректний час"
                return
            }
            this.techBreakModal.error = ""
            try {
                const res = await fetch(`/api/queue/mass-extend`, {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        minutes: mins,
                        username: cleanUsername,
                        password: this.techBreakModal.password
                    })
                })
                if (res.ok) {
                    this.techBreakModal.open = false
                    this.techBreakModal.username = ""
                    this.techBreakModal.password = ""
                    this.techBreakModal.customMinutes = ""
                    this.techBreakModal.error = ""
                    await this.fetchQueue()
                } else {this.techBreakModal.error = await this.readErrorDetail(res, "Невірний логін/пароль або помилка сервера")}
            } catch (e) {
                console.error("Помилка масового додавання часу:", e)
                this.techBreakModal.error = "Помилка мережі"
            }
        },

        // --- TICKET EDITING ---
        openEditModal(item) {
            const currentSizes = Array.isArray(item.shoe_sizes) ? [...item.shoe_sizes] : []
            this.editModal = {
                open: true,
                id: item.id,
                ticketNumber: item.ticket_number,
                duration: item.duration_minutes || 60,
                availableDurations: [30, 45, 60, 90, 120],
                sizes: [...currentSizes],
                originalSizes: [...currentSizes],
                activeTab: "figure",
                comment: item.comment || "",
                issueStatus: item.issue_status || "",
                issueNote: item.issue_note || ""
            }
            if (typeof this.fetchInventory === "function") {this.fetchInventory()}
        },

        async readErrorDetail(res, fallbackMessage) {
            const rawText = await res.text()
            if (rawText) {
                try {
                    const err = JSON.parse(rawText)
                    if (err?.detail) return String(err.detail)
                } catch {return rawText.trim()}
            }
            return `${fallbackMessage} (${res.status})`
        },

        async submitEdit() {
            if (this.editModal.sizes.length === 0) return
            try {
                const res = await fetch(`/api/queue/${this.editModal.id}`, {
                    method: "PATCH",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        duration_minutes: parseInt(this.editModal.duration),
                        shoe_sizes: this.editModal.sizes,
                        comment: this.editModal.comment,
                        issue_status: this.editModal.issueStatus || null,
                        issue_note: this.editModal.issueStatus ? (this.editModal.issueNote || null) : null
                    })
                })
                if (res.ok) {
                    this.editModal.open = false
                    await this.fetchQueue()
                    if (typeof this.fetchInventory === "function") await this.fetchInventory()
                } else {alert(await this.readErrorDetail(res, "Помилка при оновленні квитка"))}
            } catch (e) {console.error("Помилка редагування:", e)}
        },

        getEditSizeCount(size) {return this.editModal.sizes.filter(s => s === size).length},

        getEffectiveAvailable(size) {
            const stockAvailable = this.inventory[size]?.available || 0
            const originallyHeld = this.editModal.originalSizes.filter(s => s === size).length
            return stockAvailable + originallyHeld
        },

        addEditSize(size) {
            const maxAllowed = this.getEffectiveAvailable(size)
            if (this.getEditSizeCount(size) < maxAllowed) {this.editModal.sizes.push(size)}
        },

        removeEditSize(size) {
            const index = this.editModal.sizes.lastIndexOf(size)
            if (index !== -1) {this.editModal.sizes.splice(index, 1)}
        },

        clearEditSizes() {this.editModal.sizes = []},

        // --- TICKET CANCELLATION ---
        openCancelModal(item) {
            this.cancelModal = {
                open: true,
                id: item.id,
                ticketNumber: item.ticket_number,
                reason: "",
                error: ""
            }
        },

        async submitCancel() {
            if (!this.cancelModal.reason || this.cancelModal.reason.length < 3) {
                this.cancelModal.error = "Введіть причину скасування (мінімум 3 символи)."
                return
            }
            this.cancelModal.error = ""
            try {
                const res = await fetch(`/api/queue/${this.cancelModal.id}/cancel`, {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({reason: this.cancelModal.reason})
                })
                if (res.ok) {
                    this.cancelModal.open = false
                    this.cancelModal.error = ""
                    await this.fetchQueue()
                } else {this.cancelModal.error = await this.readErrorDetail(res, "Не вдалося скасувати квиток")}
            } catch (e) {console.error("Помилка скасування:", e)}
        },

        // --- STATUS & SESSION MANAGEMENT ---
        isTicketBlocked(item) {
            if (!item.shoe_sizes || !Array.isArray(item.shoe_sizes)) return false
            if (!["ЧЕКАЄ", "WAITING", "ВИКЛИКАЄТЬСЯ", "CALLING"].includes(item.status)) return false

            const requiredCounts = {}
            for (const size of item.shoe_sizes) {
                const key = String(size).trim()
                requiredCounts[key] = (requiredCounts[key] || 0) + 1
            }

            for (const [size, neededCount] of Object.entries(requiredCounts)) {
                let invKey = size
                if (!this.inventory[invKey]) {
                    const foundKey = Object.keys(this.inventory).find(k => k === size || k.startsWith(size + " ") || k.startsWith(size + "("))
                    if (foundKey) invKey = foundKey
                }

                const invData = this.inventory[invKey]
                const availableStock = invData ? (invData.available ?? 0) : 0

                if (neededCount > availableStock) {return true}
            }
            return false
        },

        async changeStatus(itemId, newStatus) {
            const item = this.queue.find(i => i.id === itemId)
            if (!item) return

            const currentStatus = item.status
            item.status = newStatus

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

        async revertStatus(itemId) {
            try {
                const response = await fetch(`/api/queue/${itemId}/revert`, {
                    method: "POST", headers: {"Content-Type": "application/json"}
                })
                if (!response.ok) {
                    const err = await response.text()
                    console.error("Помилка відновлення статусу:", err)
                    return
                }
                await this.fetchQueue()
            } catch (e) {console.error("Помилка відновлення статусу:", e)}
        },

        async toggleStopTimer(itemId) {
            try {
                const response = await fetch(`/api/queue/${itemId}/stop-timer`, {
                    method: "POST",
                    headers: {"Content-Type": "application/json"}
                })
                if (!response.ok) await this.fetchQueue()
            } catch (e) {
                console.error("Помилка зупинки таймера:", e)
                await this.fetchQueue()
            }
        },

        // Єдиний формат підпису сеансу: "90 хв • до 13:13" (або просто "90 хв", поки час закінчення невідомий)
        sessionSummary(item) {
            const duration = item.duration_minutes ? item.duration_minutes + " хв" : "—"
            return item.session_end ? `${duration} • до ${formatTime(item.session_end)}` : duration
        },

        getTimeDisplay(item) {
            const isActive = item.status === "ОБСЛУГОВУЄТЬСЯ" || item.status === "SERVED"
            if (isActive && item.session_end) {
                const remaining = getRemainingTime(item.session_end, item, this.now)
                return remaining ?? "00:00"
            }
            return item.duration_minutes ? item.duration_minutes + " хв" : "—"
        },

        async skipLacing(itemId) {
            try {
                const response = await fetch(`/api/queue/${itemId}/skip-lacing`, {
                    method: "POST",
                    headers: {"Content-Type": "application/json"}
                })
                await this.fetchQueue()
            } catch (e) {
                console.error("Помилка запуску основного часу:", e)
                await this.fetchQueue()
            }
        },

        getSessionPhase(item) {return getSessionPhase(item, this.now)},

        // --- ISSUE STATUS MANAGEMENT ---
        // Один клік: поставити позначку; повторний клік по тій самій — зняти
        toggleIssue(item, status) {
            return this.setIssueStatus(item.id, item.issue_status === status ? null : status)
        },

        async setIssueStatus(itemId, status) {
            const item = this.queue.find(i => i.id === itemId)
            const prevStatus = item ? item.issue_status : null
            const prevNote = item ? item.issue_note : null
            if (item) {
                item.issue_status = status // Миттєва зміна кольору в UI
                if (!status) item.issue_note = null
            }

            try {
                const res = await fetch(`/api/queue/${itemId}/issue`, {
                    method: "PATCH",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({issue_status: status})
                })
                if (!res.ok) {
                    if (item) {item.issue_status = prevStatus; item.issue_note = prevNote}
                    alert(await this.readErrorDetail(res, "Не вдалося оновити статус проблеми"))
                } else {await this.fetchQueue()}
            } catch (e) {
                if (item) {item.issue_status = prevStatus; item.issue_note = prevNote}
                console.error("Помилка оновлення статусу проблеми:", e)
            }
        },

        // --- LIFECYCLE ---
        async init() {
            await this.fetchInventory()
            setInterval(() => {this.now = Date.now()}, 1000)
            if (typeof this.fetchQueue === "function") await this.fetchQueue()
            this.initWebSocket()
        }
    }
}