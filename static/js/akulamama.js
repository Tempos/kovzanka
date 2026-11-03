document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.ak-nav a').forEach(link => {
        if (link.pathname === window.location.pathname) link.setAttribute('aria-current', 'page');
    });
});
