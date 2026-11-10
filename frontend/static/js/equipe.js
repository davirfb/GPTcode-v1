document.addEventListener('DOMContentLoaded', function() {
    // Animação de aparecimento ao scroll
    const members = document.querySelectorAll('.team-member');
    
    const observerOptions = {
        root: null,
        rootMargin: '0px',
        threshold: 0.1
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, observerOptions);
    
    // Observar todos os membros da equipe
    members.forEach(member => {
        observer.observe(member);
    });
    // os tooltips são iniciados pelo main.js (comportamento global)
});