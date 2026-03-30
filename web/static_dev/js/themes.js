(function() {
  const getSystemTheme = () => window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  const setTheme = (theme) => {
    document.documentElement.setAttribute('data-bs-theme', theme);
    localStorage.setItem('theme', theme);
    const icon = document.getElementById('theme-icon');
    if (icon) {
      icon.className = theme === 'dark' ? 'bi bi-moon-stars' : 'bi bi-brightness-high';
    }
  };
  const toggleTheme = () => {
    const current = document.documentElement.getAttribute('data-bs-theme');
    setTheme(current === 'dark' ? 'light' : 'dark');
  };
  const saved = localStorage.getItem('theme');
  if (saved) {
    setTheme(saved);
  } else {
    setTheme(getSystemTheme());
  }
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (!localStorage.getItem('theme')) {
      setTheme(e.matches ? 'dark' : 'light');
    }
  });
  window.themeToggle = toggleTheme;
})();