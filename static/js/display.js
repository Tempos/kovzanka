function displayApp() {
    return {
        ...queueMixin(),
        ...wsSyncMixin(),

        // --- STATE AND VARIABLES ---
        isFullscreen: false,
        now: Date.now(),
        hideCalling: false,
        hideWaiting: false,
        hideOnIce: false,
        autoHideEmpty: true,

        // --- COMPUTED PROPERTIES ---
        get callingItems() {return this.queue.filter(item => item.status === "ВИКЛИКАЄТЬСЯ")},
        get waitingItems() {return this.queue.filter(item => item.status === "ЧЕКАЄ")},
        get servedItems() {return this.queue.filter(item => item.status === "ОБСЛУГОВУЄТЬСЯ")},
        get wsStatus() {return getWsStatus(this.wsConnected)},

        get showCalling() {
            if (this.hideCalling) return false
            return !(this.autoHideEmpty && this.callingItems.length === 0)
        },
        get showWaiting() {
            if (this.hideWaiting) return false
            return !(this.autoHideEmpty && this.waitingItems.length === 0)
        },
        get showOnIce() {
            if (this.hideOnIce) return false
            return !(this.autoHideEmpty && this.servedItems.length === 0)
        },

        // --- FULLSCREEN MODE ---
        toggleFullScreen() {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen().catch(err => {console.error("Error attempting to enable full-screen mode:", err)})
            } else if (document.exitFullscreen) {document.exitFullscreen()}
        },
        getItemPeopleCount(item) {
            if (!item) return 1
            const sizes = item.shoe_sizes
            if (Array.isArray(sizes)) {return sizes.length > 0 ? sizes.length : 1}
            if (typeof sizes === "string" && sizes.trim() !== "") {
                const parts = sizes.split(",").map(s => s.trim()).filter(Boolean)
                return parts.length > 0 ? parts.length : 1
            }
            if (typeof item.people_count === "number" && item.people_count > 0) {return item.people_count}
            if (typeof item.guests_count === "number" && item.guests_count > 0) {return item.guests_count}
            return 1
        },
        sumPeople(items) {
            if (!Array.isArray(items)) return 0
            return items.reduce((sum, item) => sum + this.getItemPeopleCount(item), 0)
        },
        get callingPeopleCount() {return this.sumPeople(this.callingItems)},
        get waitingPeopleCount() {return this.sumPeople(this.waitingItems)},
        get servedPeopleCount() {return this.sumPeople(this.servedItems)},
        get totalPeopleCount() {return this.callingPeopleCount + this.waitingPeopleCount + this.servedPeopleCount},
        get totalTicketsCount() {return this.callingItems.length + this.waitingItems.length + this.servedItems.length},

        // --- LIFECYCLE ---
        init() {
            this.fetchQueue()
            setInterval(() => {this.now = Date.now()}, 1000)
            this.initWebSocket()

            document.addEventListener("fullscreenchange", () => {
                this.isFullscreen = !!document.fullscreenElement
                if (this.isFullscreen) {document.body.classList.add("fullscreen-mode")} else {document.body.classList.remove("fullscreen-mode")}
            })
        }
    }
}