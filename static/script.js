/* College0 — script.js */

// ── STAR RATING ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {

  // Interactive star rating
  const starsContainer = document.querySelector('.stars');
  if (starsContainer) {
    const stars = starsContainer.querySelectorAll('.star');
    const input = document.querySelector('input[name="star_rating"]');

    stars.forEach((star, i) => {
      star.addEventListener('mouseover', () => {
        stars.forEach((s, j) => s.classList.toggle('hover', j <= i));
      });
      star.addEventListener('mouseout', () => {
        stars.forEach(s => s.classList.remove('hover'));
        highlightStars(input ? parseInt(input.value) : 0);
      });
      star.addEventListener('click', () => {
        if (input) input.value = i + 1;
        highlightStars(i + 1);
      });
    });

    function highlightStars(n) {
      stars.forEach((s, j) => s.classList.toggle('active', j < n));
    }
  }

  // ── AUTO-DISMISS ALERTS ──────────────────────────────────────────────────
  document.querySelectorAll('.alert[data-auto-dismiss]').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity .4s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 400);
    }, 4000);
  });

  // ── CONFIRM DELETES ──────────────────────────────────────────────────────
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', e => {
      if (!confirm(el.dataset.confirm)) e.preventDefault();
    });
  });

  // ── ACTIVE NAV LINK ──────────────────────────────────────────────────────
  const path = window.location.pathname;
  document.querySelectorAll('.navbar a').forEach(a => {
    if (a.getAttribute('href') && path.startsWith(a.getAttribute('href')) && a.getAttribute('href') !== '/') {
      a.classList.add('active');
    }
  });

  // ── GRADE SELECT AUTO-COLOR ──────────────────────────────────────────────
  document.querySelectorAll('select[name="letter_grade"]').forEach(sel => {
    function colorGrade() {
      const g = sel.value;
      if (!g) return;
      if (['A+','A','A-'].includes(g)) sel.style.color = '#155724';
      else if (['B+','B','B-'].includes(g)) sel.style.color = '#004085';
      else if (['C+','C','C-'].includes(g)) sel.style.color = '#856404';
      else sel.style.color = '#721c24';
    }
    sel.addEventListener('change', colorGrade);
    colorGrade();
  });

});