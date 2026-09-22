// --- FORMATTERS ---
function formatPhone(phone) {
    if (!phone) return "—"
    let cleaned = ("" + phone).replace(/\D/g, "")
    if (cleaned.length === 12 && cleaned.startsWith("380")) {cleaned = cleaned.substring(2)}
    const match = cleaned.match(/^(\d{3})(\d{3})(\d{2})(\d{2})$/)
    return match ? `${match[1]} ${match[2]} ${match[3]} ${match[4]}` : phone
}

function formatTime(isoString) {
    const date = parseServerDate(isoString)
    if (!date) return ""
    return date.toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", hour12: false})
}

// Parses a server timestamp into a Date, unambiguously.
// The backend stores naive timestamps with NO timezone marker
// (e.g. "2026-09-18 20:11:55.800391"), but those values are UTC
// (Python's datetime.utcnow()-style naive UTC), not local time.
// If a string already carries an explicit timezone (Z or +hh:mm), trust it.
// Otherwise, parse the components explicitly as UTC — never let the
// browser's ambiguous/local-time guessing shift the instant by our
// UTC offset (this was the source of the "already 90 min overdue
// right after starting" bug).
function parseServerDate(isoString) {
    if (!isoString) return null
    if (/[Zz]|[+-]\d{2}:?\d{2}$/.test(isoString)) {
        return new Date(isoString)
    }
    const [datePart, timePart] = isoString.split(/[T ]/)
    const [year, month, day] = datePart.split("-").map(Number)
    const [hour = 0, minute = 0, second = 0] = (timePart || "").split(":").map(s => parseFloat(s))
    return new Date(Date.UTC(year, month - 1, day, hour, minute, Math.floor(second || 0)))
}

function getWsStatus(wsConnected) {
    return wsConnected
        ? {text: "ЗВ'ЯЗОК АКТИВНИЙ (WS)", class: "bg-green-500 animate-pulse"}
        : {text: "ПЕРЕПІДКЛЮЧЕННЯ...", class: "bg-amber-500"}
}

function createQueueWebSocket({onMessage, onOpen, onClose}) {
    let socket = null

    const connect = () => {
        if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {return}

        const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:"
        const wsUrl = `${wsProtocol}//${window.location.host}/api/ws/queue`
        socket = new WebSocket(wsUrl)

        socket.onopen = () => {if (onOpen) onOpen()}

        socket.onmessage = (event) => {
            if (event.data === "ping") return
            if (onMessage) onMessage(event)
        }

        socket.onerror = (error) => console.error("WebSocket error:", error)

        socket.onclose = () => {
            if (onClose) onClose()
            setTimeout(connect, 2000) // Auto-reconnect
        }
    }

    connect()
    return {get instance() { return socket }}
}
// Compact size summary for the display board: groups duplicate sizes with a
// ×count instead of repeating them, and packs as many groups as fit on one
// line (by character budget, not a flat group count) before folding the rest
// into a "+N" tail. maxChars=21 was calibrated against the actual card width
// in display.html (grid-cols-3 card at text-xs, ui-monospace) - see the
// "Розмір(и): " label shares the line with this text, so budget is tight.
function formatSizesSummary(sizes, maxChars = 21) {
    if (!sizes || sizes.length === 0) return "—"

    const counts = {}
    for (const s of sizes) counts[s] = (counts[s] || 0) + 1
    const uniqueSizes = Object.keys(counts).map(Number).sort((a, b) => a - b)
    const groupStrs = uniqueSizes.map(s => counts[s] > 1 ? `${s}×${counts[s]}` : `${s}`)

    let shown = 0, len = 0
    while (shown < groupStrs.length) {
        const addLen = (shown === 0 ? groupStrs[shown].length : 2 + groupStrs[shown].length) // ", "
        const remainingAfter = groupStrs.length - shown - 1
        // reserve room for the eventual "+N" tail, if one will still be needed after adding this group
        const shownPeopleIfAdded = uniqueSizes.slice(0, shown + 1).reduce((sum, s) => sum + counts[s], 0)
        const tailLen = remainingAfter > 0 ? 1 + String(sizes.length - shownPeopleIfAdded).length : 0
        if (len + addLen + tailLen > maxChars) break
        len += addLen
        shown++
    }

    const parts = groupStrs.slice(0, shown)
    if (shown < groupStrs.length) {
        const shownPeople = uniqueSizes.slice(0, shown).reduce((sum, s) => sum + counts[s], 0)
        parts.push(`+${sizes.length - shownPeople}`)
    }

    return parts.join(", ")
}