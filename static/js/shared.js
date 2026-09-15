// --- FORMATTERS ---
function formatPhone(phone) {
    if (!phone) return "—"
    let cleaned = ("" + phone).replace(/\D/g, "")
    if (cleaned.length === 12 && cleaned.startsWith("380")) {cleaned = cleaned.substring(2)}
    const match = cleaned.match(/^(\d{3})(\d{3})(\d{2})(\d{2})$/)
    return match ? `${match[1]} ${match[2]} ${match[3]} ${match[4]}` : phone
}

function formatTime(isoString) {
    if (!isoString) return ""
    const timePart = isoString.includes("T") ? isoString.split("T")[1] : isoString.split(" ")[1]
    return timePart ? timePart.substring(0, 5) : ""
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