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
expand.type = 'button';
expand.className = 'presentation-button expand-control';
expand.textContent = 'Ampliar control';
expand.setAttribute('aria-pressed', 'false');
document.querySelector('.remote-shell').prepend(expand);

function setExpanded(value) {
  document.body.classList.toggle('control-expanded', value);
  expand.textContent = value ? 'Restaurar tamaño' : 'Ampliar control';
  expand.setAttribute('aria-pressed', String(value));
}

expand.addEventListener('click', () => setExpanded(!document.body.classList.contains('control-expanded')));
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !dialog.open) setExpanded(false);
});
