// Sticky nav shadow on scroll
const nav = document.querySelector('.nav');
if (nav) {
  window.addEventListener('scroll', () => {
    nav.classList.toggle('scrolled', window.scrollY > 10);
  });
}

// Mobile nav toggle
const toggle = document.querySelector('.nav-toggle');
const links = document.querySelector('.nav-links');
if (toggle && links) {
  toggle.addEventListener('click', () => {
    links.classList.toggle('open');
  });
  // Close menu on link click
  links.querySelectorAll('a').forEach(a => {
    a.addEventListener('click', () => links.classList.remove('open'));
  });
}

// Intersection observer for fade-in animations
const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.1 }
);

document.querySelectorAll('.fade-in').forEach(el => observer.observe(el));

// Alumni toggle
const alumniBtn = document.querySelector('.alumni-toggle');
const alumniList = document.querySelector('.alumni-list');
if (alumniBtn && alumniList) {
  alumniBtn.addEventListener('click', () => {
    alumniList.classList.toggle('open');
    alumniBtn.textContent = alumniList.classList.contains('open')
      ? 'Hide Alumni'
      : 'Show Alumni & Where They Are Now';
  });
}
