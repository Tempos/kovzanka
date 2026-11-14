function kasa2App() {
    return {
        ...inventoryMixin(),
        ...queueMixin(),
        ...wsSyncMixin(),

        // --- STATE AND VARIABLES ---
        showInventoryModal: false,
        searchQuery: '',
        inventory: {},
        fetchTimer: null,
        now: Date.now(),

        formatPhone, formatTime,

        // --- MODALS (EDIT & CANCEL) ---
        editModal: {
            open: false,
            id: null,
            ticketNumber: '',
            duration: 60,
            availableDurations: [30, 45, 60, 90, 120],
            sizes: [],
            originalSizes: [],
            activeTab: 'figure',
            comment: ''
        },
        cancelModal: {
            open: false,
            id: null,
            ticketNumber: '',
            reason: '',
            error: ''
        },

        // --- COMPUTED PROPERTIES ---
        get filteredEditInventory() {
            const filtered = {}
            for (const [size, data] of Object.entries(this.inventory)) {
                const lower = String(size).toLowerCase()
                const isHockey = lower.includes('хок') || lower.includes('hok')

                if (this.editModal.activeTab === 'hockey' && isHockey) {filtered[size] = data}
                else if (this.editModal.activeTab === 'figure' && !isHockey) {filtered[size] = data}
            }
            return filtered
        },

        get activeQueue() {
            let items = this.queue.filter(i =>
                ['ЧЕКАЄ', 'ВИКЛИКАЄТЬСЯ', 'ОБСЛУГОВУЄТЬСЯ', 'WAITING', 'CALLING', 'SERVED'].includes(i.status)
            );

            if (!this.searchQuery || this.searchQuery.trim() === '') {return items;}

            const q = this.searchQuery.trim().toLowerCase();
            return items.filter(item => {
                if (String(item.ticket_number).includes(q)) return true;
                if (item.phone && String(item.phone).toLowerCase().includes(q)) return true;
                const formattedPh = formatPhone(item.phone);
                if (formattedPh && formattedPh.toLowerCase().includes(q)) return true;
                if (item.comment && String(item.comment).toLowerCase().includes(q)) return true;
                if (item.shoe_sizes && Array.isArray(item.shoe_sizes)) {
                    if (item.shoe_sizes.some(sz => String(sz).toLowerCase().includes(q))) return true;
                }
                return false;
            });
        },

        get closedQueue() {
            return this.queue.filter(i =>
                ['ПОВЕРНЕНО', 'СКАСОВАНО', 'RETURNED', 'CANCELLED'].includes(i.status)
            )
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
                activeTab: 'figure',
                comment: item.comment || ''
            }
            if (typeof this.fetchInventory === 'function') {this.fetchInventory()}
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

        async submitEdit() {
            if (this.editModal.sizes.length === 0) return
            try {
                const res = await fetch(`/api/queue/${this.editModal.id}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        duration_minutes: parseInt(this.editModal.duration),
                        shoe_sizes: this.editModal.sizes,
                        comment: this.editModal.comment
                    })
                })
                if (res.ok) {
                    this.editModal.open = false
                    await this.fetchQueue()
                    if (typeof this.fetchInventory === 'function') await this.fetchInventory()
                } else {
                    const err = await res.json()
                    alert(err.detail || 'Помилка при оновленні квитка')
                }
            } catch (e) {console.error("Помилка редагування:", e)}
        },

        // --- TICKET CANCELLATION ---
        openCancelModal(item) {
            this.cancelModal = {
                open: true,
                id: item.id,
                ticketNumber: item.ticket_number,
                reason: '',
                error: ''
            };
        },

        async submitCancel() {
            if (!this.cancelModal.reason || this.cancelModal.reason.length < 3) {
                this.cancelModal.error = 'Введіть причину скасування (мінімум 3 символи).';
                return;
            }
            try {
                const res = await fetch(`/api/queue/${this.cancelModal.id}/cancel`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ reason: this.cancelModal.reason })
                });
                if (res.ok) {
                    this.cancelModal.open = false;
                    await this.fetchQueue();
                } else {
                    const err = await res.json();
                    this.cancelModal.error = err.detail || 'Не вдалося скасувати квиток';
                }
            } catch (e) {console.error("Помилка скасування:", e);}
        },

        // --- STATUS & SESSION MANAGEMENT ---
        async fetchInventory() {
            try {
                const res = await fetch("/api/inventory")
                if (res.ok) {
                    const rawData = await res.json()
                    const sortedKeys = Object.keys(rawData).sort((a, b) =>
                        a.localeCompare(b, undefined, {numeric: true, sensitivity: 'base'})
                    )
                    const sortedInventory = {}
                    sortedKeys.forEach(key => {sortedInventory[key] = rawData[key]})
                    this.inventory = sortedInventory
                }
            } catch (e) {console.error("Помилка завантаження залишків у Касі 2:", e)}
        },

        isTicketBlocked(item) {
            if (!item.shoe_sizes || !Array.isArray(item.shoe_sizes)) return false;
            if (item.status !== 'ЧЕКАЄ' && item.status !== 'WAITING') return false;

            const requiredCounts = {};
            for (const size of item.shoe_sizes) {
                const key = String(size);
                requiredCounts[key] = (requiredCounts[key] || 0) + 1;
            }

            for (const [size, neededCount] of Object.entries(requiredCounts)) {
                let invKey = size;
                if (!this.inventory[invKey]) {
                    const candidate = `${size} (фігурні)`;
                    if (this.inventory[candidate]) invKey = candidate;
                }

                const invData = this.inventory[invKey];
                const availableStock = invData ? (invData.available ?? 0) : 0;

                if (neededCount > availableStock) {return true;}
            }
            return false;
        },

        get wsStatus() {return getWsStatus(this.wsConnected)},

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

        // --- TIMERS & TIME FORMATTING ---
        getOverdueMinutes(sessionEndIso) {
            if (!sessionEndIso) return 0
            const endTime = parseServerDate(sessionEndIso)?.getTime()
            if (!endTime) return 0
            const diffMinutes = Math.floor((this.now - endTime) / (1000 * 60))
            return diffMinutes > 0 ? diffMinutes : 0
        },

        getRemainingTime(sessionEndIso) {
            const end = parseServerDate(sessionEndIso)
            if (!end) return null
            const diffMs = end.getTime() - this.now
            if (diffMs <= 0) return null
            return formatMs(diffMs)
        },

        getOverdueTime(sessionEndIso) {
            const end = parseServerDate(sessionEndIso)
            if (!end) return null
            const diffMs = this.now - end.getTime()
            if (diffMs <= 0) return null
            return formatMs(diffMs)
        },

        getTimeDisplay(item) {
            const isActive = item.status === "ОБСЛУГОВУЄТЬСЯ" || item.status === "SERVED"
            if (isActive && item.session_end) {
                const remaining = this.getRemainingTime(item.session_end)
                return remaining ?? "00:00"
            }
            return item.duration_minutes ? item.duration_minutes + " хв" : "—"
        },

        // --- LIFECYCLE ---
        async init() {
            this.initInventory()
            if (typeof this.fetchQueue === "function") await this.fetchQueue()
            setInterval(() => {this.now = Date.now()}, 1000)
            this.initWebSocket()
        }
    }
}