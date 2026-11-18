function displayApp() {
    return {
        ...queueMixin(),
        ...wsSyncMixin(),

        // --- STATE AND VARIABLES ---
        isFullscreen: false,
        now: Date.now(),
        hideOnIce: false,

        // --- COMPUTED PROPERTIES ---
        get callingItems() {return this.queue.filter(item => item.status === "ВИКЛИКАЄТЬСЯ")},
        get waitingItems() {return this.queue.filter(item => item.status === "ЧЕКАЄ")},
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

        // --- LIFECYCLE ---
        init() {
            this.fetchQueue()
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