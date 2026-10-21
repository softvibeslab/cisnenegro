/* Fondo decorativo: reproducción silenciosa, pausa accesible y carga según preferencias. */
(function () {
  'use strict';

  var hero = document.querySelector('.hero--video');
  if (!hero) return;
  var video = hero.querySelector('video');
  var button = hero.querySelector('.hero__video-control');
  if (!video || !button) return;

  var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  var connection = navigator.connection;
  var rect = hero.getBoundingClientRect();
  var inView = rect.bottom > 0 && rect.top < window.innerHeight;
  var wantsPlayback = !reducedMotion.matches && !(connection && connection.saveData);
  var pending = false;
  var failed = false;

  video.muted = true;
  video.defaultMuted = true;
  button.hidden = false;

  function updateButton() {
    button.querySelector('[data-video-label]').textContent = video.paused ? 'Reproducir video' : 'Pausar video';
    button.querySelector('[data-video-icon]').textContent = video.paused ? '▶' : 'Ⅱ';
  }

  function canPlay() { return wantsPlayback && inView && !document.hidden && !failed; }

  function sync() {
    if (!canPlay()) {
      video.pause();
      updateButton();
      return;
    }
    if (!video.paused || pending) return;
    if (!video.getAttribute('src')) {
      video.src = window.matchMedia('(max-width: 767px)').matches ? video.dataset.mobileSrc : video.dataset.src;
      video.load();
    }
    pending = true;
    var interrupted = false;
    Promise.resolve(video.play()).catch(function (error) {
      // pause() puede cancelar un play() pendiente al salir de pantalla.
      // Conserva la intención para reanudar cuando vuelva a estar visible.
      if (error && error.name === 'AbortError') {
        interrupted = true;
        return;
      }
      // Si el navegador bloquea autoplay, la foto y el botón siguen funcionando.
      wantsPlayback = false;
      video.classList.remove('is-ready');
    }).finally(function () {
      pending = false;
      updateButton();
      if (interrupted && canPlay()) sync();
    });
  }

  video.addEventListener('playing', function () {
    // Cubre cambios de pestaña o preferencias mientras play() estaba pendiente.
    if (!canPlay()) { video.pause(); return; }
    video.classList.add('is-ready');
    updateButton();
  });
  video.addEventListener('pause', updateButton);
  video.addEventListener('error', function () {
    failed = true;
    wantsPlayback = false;
    video.pause();
    video.classList.remove('is-ready');
    button.hidden = true;
  });

  button.addEventListener('click', function () {
    wantsPlayback = video.paused;
    sync();
  });
  document.addEventListener('visibilitychange', sync);

  function respectPreference() {
    if (reducedMotion.matches || (connection && connection.saveData)) {
      wantsPlayback = false;
      video.classList.remove('is-ready');
      sync();
    }
  }
  reducedMotion.addEventListener('change', respectPreference);
  if (connection && connection.addEventListener) connection.addEventListener('change', respectPreference);

  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (entries) {
      inView = entries[0].isIntersecting;
      sync();
    }, { threshold: 0 }).observe(hero);
  }
  sync();
})();
