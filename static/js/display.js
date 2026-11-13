function displayApp() {
    return {
        ...queueMixin(),
        ...wsSyncMixin(),

        isFullscreen: false,
        now: Date.now(),

        get callingItems() {return this.queue.filter(item => item.status === "ВИКЛИКАЄТЬСЯ")},
        get waitingItems() {return this.queue.filter(item => item.status === "ЧЕКАЄ").slice(0, 12)},
        get servedItems() {return this.queue.filter(item => item.status === "ОБСЛУГОВУЄТЬСЯ")},

        get wsStatus() {return getWsStatus(this.wsConnected)},

        toggleFullScreen() {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen().catch(err => {
                    console.error("Error attempting to enable full-screen mode:", err)
                });
            } else if (document.exitFullscreen) {document.exitFullscreen();}
        },

        formatMs(diffMs) {
            const totalSeconds = Math.floor(diffMs / 1000)
            const minutes = Math.floor(totalSeconds / 60)
            const seconds = totalSeconds % 60
            return `${minutes}:${seconds.toString().padStart(2, "0")}`
        },

        getRemainingTime(sessionEndIso) {
            const end = typeof parseServerDate === 'function' ? parseServerDate(sessionEndIso) : new Date(sessionEndIso)
            if (!end) return null
            const diffMs = end.getTime() - this.now
            if (diffMs <= 0) {
                // Показує перевищення часу у форматі протермінування
                const overdueMs = Math.abs(diffMs)
                return '+' + this.formatMs(overdueMs)
            }
            return this.formatMs(diffMs)
        },

        isOverdue(sessionEndIso) {
            if (!sessionEndIso) return false
            const end = typeof parseServerDate === 'function' ? parseServerDate(sessionEndIso) : new Date(sessionEndIso)
            return end ? (this.now - end.getTime()) > 0 : false
        },

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