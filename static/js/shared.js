// 1. FORMATTERS AND DATES
function formatPhone(phone) {
    if (!phone) return "—"
    let cleaned = ("" + phone).replace(/\D/g, "")
    if (cleaned.length === 12 && cleaned.startsWith("380")) { cleaned = cleaned.substring(2) }
    const match = cleaned.match(/^(\d{3})(\d{3})(\d{2})(\d{2})$/)
    return match ? `${match[1]} ${match[2]} ${match[3]} ${match[4]}` : phone
}

function formatTime(isoString) {
    const date = parseServerDate(isoString)
    if (!date) return ""
    return date.toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", hour12: false})
}

function parseServerDate(isoString) {
    if (!isoString) return null
    if (/[Zz]|[+-]\d{2}:?\d{2}$/.test(isoString)) {
        const date = new Date(isoString)
        return Number.isNaN(date.getTime()) ? null : date
    }
    const [datePart, timePart] = isoString.split(/[T ]/)
    const [year, month, day] = datePart.split("-").map(Number)
    const [hour = 0, minute = 0, second = 0] = (timePart || "").split(":").map(s => parseFloat(s))
    const date = new Date(Date.UTC(year, month - 1, day, hour, minute, Math.floor(second || 0)))
    return Number.isNaN(date.getTime()) ? null : date
}


// 2. WEBSOCKET & STATUSES
function getWsStatus(wsConnected) {
    return wsConnected
        ? {title: "ЗВ'ЯЗОК АКТИВНИЙ (WS)", class: "bg-green-500 animate-pulse"}
        : {text: "ПЕРЕПІДКЛЮЧЕННЯ...", class: "bg-amber-500"}
}

function createQueueWebSocket({onMessage, onOpen, onClose}) {
    let socket = null

    const connect = () => {
        if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) { return }

        const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:"
        const wsUrl = `${wsProtocol}//${window.location.host}/api/ws/queue`
        socket = new WebSocket(wsUrl)

        socket.onopen = () => { if (onOpen) onOpen() }
        socket.onmessage = (event) => {
            if (event.data === "ping") return
            if (onMessage) onMessage(event)
        }
        socket.onerror = (error) => console.error("WebSocket error:", error)
        socket.onclose = () => {
            if (onClose) onClose()
            setTimeout(connect, 2000)
        }
    }

    connect()
    return {get instance() { return socket }}
}


// 3. SIZES AND TIME HELPERS
function parseSizeNum(key) {
    const match = String(key).match(/^(\d+)/)
    return match ? match[1] : key
}

function parseSizeCat(key) {
    const lower = String(key).toLowerCase()
    if (lower.includes("хок") || lower.includes("hok")) return "(хок.)"
    if (lower.includes("фіг")) return "(фіг.)"
    const match = String(key).match(/\((.*?)\)/)
    return match ? `(${match[1]})` : ""
}

function formatMs(diffMs) {
    const totalSeconds = Math.floor(diffMs / 1000)
    const minutes = Math.floor(totalSeconds / 60)
    const seconds = totalSeconds % 60
    return `${minutes}:${seconds.toString().padStart(2, "0")}`
}

function formatSizeKey(key) {
    const match = String(key).match(/^(\d+)\s*\((.*?)\)$/)
    if (!match) return key
    const [_, num, cat] = match
    const shortCat = cat.startsWith("фіг") ? "фіг." : (cat.startsWith("хок") ? "хок." : cat)
    return `${num} (${shortCat})`
}

function formatSizesSummary(sizes, maxChars = 105) {
    if (typeof sizes === "string") {
        try {sizes = JSON.parse(sizes)} catch (e) {sizes = sizes ? [sizes] : []}
    }

    if (!sizes || sizes.length === 0) return "—"

    const counts = {}
    for (const s of sizes) counts[s] = (counts[s] || 0) + 1

    const groupStrs = Object.entries(counts).map(([s, count]) => {
        const formatted = formatSizeKey(s)
        return count > 1 ? `${formatted}×${count}` : `${formatted}`
    })

    let result = ""
    for (const part of groupStrs) {
        const candidate = result ? `${result}, ${part}` : part
        if (candidate.length > maxChars) {
            if (!result) {return part.length > maxChars ? part.substring(0, maxChars - 1) + "…" : part}
            return `${result}…`
        }
        result = candidate
    }
    return result
}

function getEffectiveNow(item, nowMs = Date.now()) {
    if (item && item.overtime_stopped_at) {
        const stoppedMs = parseServerDate(item.overtime_stopped_at)?.getTime()
        if (stoppedMs) return stoppedMs
    }
    return nowMs
}

function getSessionPhase(item, nowMs = Date.now()) {
    if (!item) return null
    const effectiveNow = getEffectiveNow(item, nowMs)
    const isFrozen = Boolean(item.overtime_stopped_at)

    if (item.status === "ВИКЛИКАЄТЬСЯ" || item.status === "CALLING") {
        if (!item.called_at) return null
        const calledMs = parseServerDate(item.called_at)?.getTime()
        if (!calledMs) return null
        const deadline = calledMs + 5 * 60 * 1000
        const diff = deadline - nowMs
        return {
            phase: "CALLING",
            label: diff > 0 ? "⏳ На явку" : "⚠️ Запізнення",
            time: formatMs(Math.abs(diff)),
            overdue: diff <= 0
        }
    }

    if ((item.status === "ОБСЛУГОВУЄТЬСЯ" || item.status === "SERVED") && item.session_end) {
        const endMs = parseServerDate(item.session_end)?.getTime()
        if (!endMs) return null
        const durationMs = (item.duration_minutes || 60) * 60 * 1000
        const lacingEndMs = endMs - durationMs

        if (item.session_start && effectiveNow < lacingEndMs) {
            return {
                phase: "LACING",
                label: isFrozen ? "⏸️ Перевзування (пауза)" : "👟 Перевзування",
                time: formatMs(lacingEndMs - effectiveNow),
                overdue: false,
                frozen: isFrozen
            }
        }

        const remaining = endMs - effectiveNow
        return {
            phase: "SKATING",
            label: isFrozen
                ? (remaining > 0 ? "⏸️ Зупинено" : "⏸️ Overtime зафіксовано")
                : (remaining > 0 ? "⛸️ На льоду" : "Час вийшов!"),
            time: formatMs(Math.abs(remaining)),
            overdue: remaining <= 0,
            frozen: isFrozen
        }
    }
    return null
}

function getRemainingTime(sessionEndIso, item = null, nowMs = Date.now()) {
    const end = parseServerDate(sessionEndIso)
    if (!end) return null
    const refNow = getEffectiveNow(item, nowMs)
    const diffMs = end.getTime() - refNow
    if (diffMs <= 0) {
        const overdueMs = Math.abs(diffMs)
        return "+" + formatMs(overdueMs)
    }
    return formatMs(diffMs)
}

function getOverdueTime(sessionEndIso, item = null, nowMs = Date.now()) {
    const end = parseServerDate(sessionEndIso)
    if (!end) return null
    const refNow = getEffectiveNow(item, nowMs)
    const diffMs = refNow - end.getTime()
    if (diffMs <= 0) return null
    return formatMs(diffMs)
}

function isOverdue(sessionEndIso, item = null, nowMs = Date.now()) {
    if (!sessionEndIso) return false
    const end = parseServerDate(sessionEndIso)
    const refNow = getEffectiveNow(item, nowMs)
    return end ? (refNow - end.getTime()) > 0 : false
}


// 4. ALPINE.JS MIXINS
function inventoryMixin() {
    return {
        inventory: {},
        showInventoryModal: false,
        inventoryNow: Math.floor(Date.now() / 1000),

        initInventory() {
            void this.fetchInventory()
            setInterval(() => { this.inventoryNow = Math.floor(Date.now() / 1000) }, 1000)
            setInterval(() => { if (!document.hidden) { void this.fetchInventory() } }, 5000)
        },

        async fetchInventory() {
            try {
                const res = await fetch("/api/inventory")
                if (res.ok) { this.inventory = await res.json() }
            } catch (e) { console.error("Помилка завантаження залишків:", e) }
        },

        formatCountdown(targetTimestamp) {
            if (!targetTimestamp) return "—"
            const diff = targetTimestamp - this.inventoryNow
            if (diff <= 0) return "0 с"

            const mins = Math.floor(diff / 60)
            const secs = diff % 60
            return mins > 0 ? `${mins} хв ${String(secs).padStart(2, "0")} с` : `${secs} с`
        }
    }
}

function queueMixin() {
    return {
        queue: [],
        async fetchQueue() {
            try {
                const res = await fetch("/api/queue")
                if (res.ok) { this.queue = await res.json() }
            } catch (e) { console.error("Помилка завантаження черги:", e) }
        }
    }
}

function wsSyncMixin() {
    return {
        wsConnected: false,
        socket: null,

        get wsStatus() { return getWsStatus(this.wsConnected) },

        initWebSocket() {
            const wsWrapper = createQueueWebSocket({
                onOpen: () => {
                    this.wsConnected = true
                    if (typeof this.fetchQueue === "function") void this.fetchQueue()
                    if (typeof this.fetchInventory === "function") void this.fetchInventory()
                },
                onMessage: () => {
                    if (typeof this.fetchQueue === "function") void this.fetchQueue()
                    if (typeof this.fetchInventory === "function") void this.fetchInventory()
                },
                onClose: () => { this.wsConnected = false }
            })
            this.socket = wsWrapper.instance
        }
    }
}
