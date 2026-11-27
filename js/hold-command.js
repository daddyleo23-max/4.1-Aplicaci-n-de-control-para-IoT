// Un botón de movimiento actúa sólo mientras se mantiene pulsado.
export function bindHoldCommand(button, command, onCommand, onStop, signal) {
  let held = false;
  let pointer = null;
  let suppressClickUntil = 0;
  const on = (target, type, handler) => target.addEventListener(type, handler, { signal });
  const start = (event) => {
    if (button.disabled || held || (event.type === 'pointerdown' && event.button !== 0)) return;
    event.preventDefault();
    held = true;
    suppressClickUntil = performance.now() + 700;
    button.dataset.pressed = 'true';
    if (event.type === 'pointerdown') {
      pointer = event.pointerId;
      try { button.setPointerCapture?.(pointer); } catch { /* La cancelación también detiene. */ }
    }
    onCommand(command);
  };
  const release = (event) => {
    if (!held || (event?.type === 'pointerup' && pointer !== event.pointerId)) return;
    held = false;
    pointer = null;
    suppressClickUntil = performance.now() + 700;
    delete button.dataset.pressed;
    onStop();
  };
  on(button, 'pointerdown', start);
  on(button, 'pointerup', release);
  on(button, 'pointercancel', release);
  on(button, 'lostpointercapture', release);
  on(button, 'blur', release);
  on(button, 'keydown', event => {
    if (!event.repeat && [' ', 'Enter'].includes(event.key)) start(event);
  });
  on(button, 'keyup', event => {
    if ([' ', 'Enter'].includes(event.key)) { event.preventDefault(); release(event); }
  });
  on(button, 'click', event => {
    event.preventDefault();
    // Un clic de accesibilidad sin una secuencia pointer/teclado se trata como toque.
    if (held || performance.now() < suppressClickUntil || event.detail !== 0 || button.disabled) return;
    onCommand(command); onStop();
  });
  on(window, 'blur', release);
  on(document, 'visibilitychange', () => { if (document.hidden) release(); });
  signal.addEventListener('abort', release, { once: true });
}
