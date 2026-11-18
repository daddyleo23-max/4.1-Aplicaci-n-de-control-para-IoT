const panel = document.querySelector('.demo-panel');
const originalParent = panel.parentElement;
const originalNext = panel.nextSibling;
const dialog = document.createElement('dialog');
dialog.className = 'demo-dialog';
dialog.setAttribute('aria-label', 'Seleccionar y ejecutar DEMO');
const close = document.createElement('button');
close.type = 'button';
close.className = 'presentation-button';
close.textContent = 'Cerrar';
close.addEventListener('click', () => dialog.close());
dialog.append(close);
document.body.append(dialog);

export function openDemoPanel() {
  dialog.append(panel);
  dialog.showModal();
}

dialog.addEventListener('close', () => {
  originalParent.insertBefore(panel, originalNext);
});

const expand = document.createElement('button');
const desktop = window.matchMedia('(min-width:1001px) and (hover:hover) and (pointer:fine)');
expand.type = 'button';
expand.className = 'presentation-button expand-control';
expand.textContent = 'Ampliar control';
expand.setAttribute('aria-pressed', 'false');
expand.dataset.icon = '⛶';
document.querySelector('.remote-shell').prepend(expand);

function setExpanded(value) {
  value = value && desktop.matches;
  document.body.classList.toggle('control-expanded', value);
  expand.textContent = value ? 'Restaurar tamaño' : 'Ampliar control';
  expand.dataset.icon = value ? '↙' : '⛶';
  expand.setAttribute('aria-pressed', String(value));
}

expand.addEventListener('click', () => setExpanded(!document.body.classList.contains('control-expanded')));
desktop.addEventListener('change', () => setExpanded(false));
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !dialog.open) setExpanded(false);
});
