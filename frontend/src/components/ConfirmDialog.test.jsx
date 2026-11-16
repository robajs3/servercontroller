import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import ConfirmDialog from './ConfirmDialog.jsx';

const setup = ({ children = <p>Treść okna</p>, ...props } = {}) => {
  const onConfirm = vi.fn();
  const onCancel = vi.fn();
  const view = render(
    <ConfirmDialog open title="Wyłączyć Serwer?" confirmLabel="Wyłącz" onConfirm={onConfirm} onCancel={onCancel} {...props}>
      {children}
    </ConfirmDialog>,
  );
  return { onConfirm, onCancel, ...view };
};

describe('ConfirmDialog', () => {
  it('zamknięty nie jest widoczny', () => {
    setup({ open: false });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('otwarty pokazuje tytuł i zawartość, a tytuł nazywa okno', () => {
    setup();
    const dlg = screen.getByRole('dialog');
    expect(dlg).toHaveAccessibleName('Wyłączyć Serwer?');
    expect(screen.getByText('Treść okna')).toBeVisible();
  });

  it('otwiera się jako modalny (showModal) po zmianie open', () => {
    const spy = vi.spyOn(HTMLDialogElement.prototype, 'showModal');
    const { rerender } = setup({ open: false });
    expect(spy).not.toHaveBeenCalled();
    rerender(<ConfirmDialog open title="T" onConfirm={() => {}} onCancel={() => {}} />);
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('przycisk potwierdzenia wywołuje onConfirm, a Anuluj onCancel', async () => {
    const user = userEvent.setup();
    const { onConfirm, onCancel } = setup();
    await user.click(screen.getByRole('button', { name: 'Wyłącz' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole('button', { name: 'Anuluj' }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('Enter w polu formularza potwierdza', async () => {
    const user = userEvent.setup();
    const { onConfirm } = setup({ children: <input aria-label="Hasło" /> });
    await user.type(screen.getByLabelText('Hasło'), 'x{Enter}');
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('Esc (zdarzenie cancel) woła onCancel i nie zamyka okna samo', () => {
    const { onCancel } = setup();
    const dlg = screen.getByRole('dialog');
    const ev = new Event('cancel', { cancelable: true });
    fireEvent(dlg, ev);
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(ev.defaultPrevented).toBe(true);
  });

  it('busy blokuje oba przyciski', () => {
    setup({ busy: true });
    expect(screen.getByRole('button', { name: 'Wyłącz' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Anuluj' })).toBeDisabled();
  });

  it('danger nadaje przyciskowi potwierdzenia klasę danger', () => {
    setup({ danger: true });
    expect(screen.getByRole('button', { name: 'Wyłącz' })).toHaveClass('danger');
  });
});