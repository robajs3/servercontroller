import { useEffect, useId, useRef } from 'react';

// Okno potwierdzenia na natywnym <dialog>. Zawartość (np. pole hasła) przekazujemy jako children.
export default function ConfirmDialog({ open, title, confirmLabel = 'Potwierdź', danger, busy, onConfirm, onCancel, children }) {
  const ref = useRef(null);
  const titleId = useId();

  useEffect(() => {
    const d = ref.current;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  const submit = e => { e.preventDefault(); onConfirm(); };
  // Esc: nie pozwalamy dialogowi zamknąć się samemu, stan trzyma rodzic
  const cancel = e => { e.preventDefault(); onCancel(); };

  return (
    <dialog ref={ref} className="dialog" aria-labelledby={titleId} onCancel={cancel}>
      <form onSubmit={submit}>
        <h3 id={titleId}>{title}</h3>
        {children}
        <div className="dlg-btns">
          <button type="button" className="ghost" onClick={onCancel} disabled={busy}>Anuluj</button>
          <button className={danger ? 'danger' : ''} disabled={busy}>{confirmLabel}</button>
        </div>
      </form>
    </dialog>
  );
}