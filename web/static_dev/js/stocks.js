document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('stockSearch');
    if (searchInput) {
        searchInput.addEventListener('input', function(e) {
            const query = e.target.value.toLowerCase().trim();
            document.querySelectorAll('.stock-card-item').forEach(card => {
                const name = card.querySelector('h5').innerText.toLowerCase();
                const ticker = card.querySelector('.text-primary').innerText.toLowerCase();
                card.style.display = (name.includes(query) || ticker.includes(query)) ? 'block' : 'none';
            });
        });
    }

    const refreshForm = document.querySelector('form[action*="refresh_all"]');
    if (refreshForm) {
        refreshForm.addEventListener('submit', () => {
            refreshForm.querySelector('i').classList.add('spinning');
        });
    }
});