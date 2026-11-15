function displayApp() {
    return {
        ...queueMixin(),
        ...wsSyncMixin(),

        // --- STATE AND VARIABLES ---
        isFullscreen: false,
        now: Date.now(),

        // --- COMPUTED PROPERTIES ---
        get callingItems() {return this.queue.filter(item => item.status === "ВИКЛИКАЄТЬСЯ")},
        get waitingItems() {return this.queue.filter(item => item.status === "ЧЕКАЄ").slice(0, 12)},
        get servedItems() {return this.queue.filter(item => item.status === "ОБСЛУГОВУЄТЬСЯ")},
        get wsStatus() {return getWsStatus(this.wsConnected)},

        // --- FULLSCREEN MODE ---
        toggleFullScreen() {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen().catch(err => {
                    console.error("Error attempting to enable full-screen mode:", err)
                });
            } else if (document.exitFullscreen) {document.exitFullscreen();}
        },

        // --- TIMERS AND COUNTDOWN ---
        getRemainingTime(sessionEndIso, item = null) {
            const end = typeof parseServerDate === "function" ? parseServerDate(sessionEndIso) : new Date(sessionEndIso)
            if (!end) return null
            const refNow = getEffectiveNow(item, this.now)
            const diffMs = end.getTime() - refNow
            if (diffMs <= 0) {
                const overdueMs = Math.abs(diffMs)
                return "+" + formatMs(overdueMs)
            }
            return formatMs(diffMs)
        },

        isOverdue(sessionEndIso, item = null) {
            if (!sessionEndIso) return false
            const end = typeof parseServerDate === "function" ? parseServerDate(sessionEndIso) : new Date(sessionEndIso)
            const refNow = getEffectiveNow(item, this.now)
            return end ? (refNow - end.getTime()) > 0 : false
        },

        // --- LIFECYCLE ---
        init() {
            this.fetchQueue()
            setInterval(() => {this.fetchQueue()}, 3000)
            setInterval(() => {this.now = Date.now()}, 1000)
            this.initWebSocket()

            document.addEventListener('fullscreenchange', () => {
                this.isFullscreen = !!document.fullscreenElement;
                if (this.isFullscreen) {document.body.classList.add('fullscreen-mode')}
                else {document.body.classList.remove('fullscreen-mode')}
            });
        }
    }
}
