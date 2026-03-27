(function () {
    const errorBox = document.getElementById("gate-error");
    const passwordInput = document.getElementById("password");
    const submitBtn = document.getElementById("site-gate-submit");
    const countdownEl = document.getElementById("site-gate-countdown");

    if (!errorBox) return;

    let lockedSeconds = parseInt(errorBox.dataset.lockedSeconds || "0", 10);
    if (Number.isNaN(lockedSeconds) || lockedSeconds <= 0) return;

    function formatMMSS(totalSeconds) {
        const mm = Math.floor(totalSeconds / 60);
        const ss = totalSeconds % 60;
        return `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
    }

    function setLockedState(isLocked) {
        if (passwordInput) passwordInput.disabled = isLocked;
        if (submitBtn) submitBtn.disabled = isLocked;
    }

    function tick() {
        if (lockedSeconds <= 0) {
            if (countdownEl) countdownEl.textContent = "";
            setLockedState(false);
            return;
        }

        if (countdownEl) countdownEl.textContent = ` (${formatMMSS(lockedSeconds)})`;
        lockedSeconds -= 1;
        setTimeout(tick, 1000);
    }

    setLockedState(true);
    tick();
})();
