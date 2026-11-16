import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../api.js', () => ({ get: vi.fn(), action: vi.fn() }));
import { action, get } from '../api.js';
import StatusCard from './StatusCard.jsx';

const status = (over = {}) => ({
  stale: false, host: '192.168.1.10', state: 'ONLINE', since: null,
  icmp_ok: true, icmp_ms: 1.2, tcp_ok: true, tcp_ms: 2.4, ...over,
});
const show = async (over) => {
  get.mockResolvedValue(status(over));
  render(<StatusCard name="Serwer główny" />);
  await screen.findByText(over?.state ?? 'ONLINE', { exact: false });
};
const wake = () => screen.getByRole('button', { name: 'Włącz (WoL)' });
const shutdown = () => screen.getByRole('button', { name: 'Wyłącz' });

beforeEach(() => { vi.resetAllMocks(); });

describe('StatusCard: przyciski zależne od stanu', () => {
  it('ONLINE: aktywne tylko Wyłącz', async () => {
    await show({ state: 'ONLINE' });
    expect(wake()).toBeDisabled();
    expect(shutdown()).toBeEnabled();
  });

  it('OFFLINE: aktywne tylko Włącz', async () => {
    await show({ state: 'OFFLINE', icmp_ok: false, tcp_ok: false });
    expect(wake()).toBeEnabled();
    expect(shutdown()).toBeDisabled();
  });

  it.each(['BOOTING', 'SHUTTING_DOWN'])('%s (stan przejściowy): oba przyciski nieaktywne', async state => {
    get.mockResolvedValue(status({ state }));
    render(<StatusCard name="Serwer główny" />);
    await screen.findByText(/…/);
    expect(wake()).toBeDisabled();
    expect(shutdown()).toBeDisabled();
  });

  it('brak danych (stale): pokazuje BRAK DANYCH, Wyłącz nieaktywne', async () => {
    get.mockResolvedValue(status({ stale: true }));
    render(<StatusCard name="Serwer główny" />);
    expect(await screen.findByText('BRAK DANYCH')).toBeVisible();
    expect(shutdown()).toBeDisabled();
  });
});

describe('StatusCard: stany ładowania i błędu', () => {
  it('po odpowiedzi pokazuje dane i znacznik aktualizacji', async () => {
    await show({ state: 'ONLINE' });
    expect(await screen.findByText(/Zaktualizowano/)).toBeVisible();
  });

  it('błąd pobierania pokazuje komunikat', async () => {
    get.mockRejectedValue(new Error('brak połączenia z panelem'));
    render(<StatusCard name="Serwer główny" />);
    expect(await screen.findByText('brak połączenia z panelem')).toBeVisible();
  });
});

describe('StatusCard: wyłączanie przez ConfirmDialog', () => {
  it('okno zawiera nazwę serwera i nie wysyła nic przed potwierdzeniem', async () => {
    const user = userEvent.setup();
    await show({ state: 'ONLINE' });
    await user.click(shutdown());
    expect(screen.getByRole('dialog')).toHaveAccessibleName('Wyłączyć Serwer główny?');
    expect(action).not.toHaveBeenCalled();
  });

  it('Anuluj zamyka okno i niczego nie wysyła', async () => {
    const user = userEvent.setup();
    await show({ state: 'ONLINE' });
    await user.click(shutdown());
    await user.click(screen.getByRole('button', { name: 'Anuluj' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(action).not.toHaveBeenCalled();
  });

  it('potwierdzenie wysyła hasło, zamyka okno i pokazuje komunikat', async () => {
    const user = userEvent.setup();
    action.mockResolvedValue({ ok: true, message: 'Wysłano polecenie wyłączenia.' });
    await show({ state: 'ONLINE' });
    await user.click(shutdown());
    await user.type(screen.getByLabelText('Hasło do konta'), 'tajne');
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Wyłącz' }));
    await waitFor(() => expect(action).toHaveBeenCalledWith('/api/actions/shutdown', { password: 'tajne' }));
    expect(await screen.findByText('Wysłano polecenie wyłączenia.')).toBeVisible();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('błąd (złe hasło) pokazuje komunikat z rolą alert', async () => {
    const user = userEvent.setup();
    action.mockResolvedValue({ ok: false, message: 'Nieprawidłowe hasło.' });
    await show({ state: 'ONLINE' });
    await user.click(shutdown());
    await user.type(screen.getByLabelText('Hasło do konta'), 'zle');
    await user.keyboard('{Enter}');
    expect(await screen.findByRole('alert')).toHaveTextContent('Nieprawidłowe hasło.');
  });

  it('po anulowaniu hasło nie zostaje w polu przy ponownym otwarciu', async () => {
    const user = userEvent.setup();
    await show({ state: 'ONLINE' });
    await user.click(shutdown());
    await user.type(screen.getByLabelText('Hasło do konta'), 'tajne');
    await user.click(screen.getByRole('button', { name: 'Anuluj' }));
    await user.click(shutdown());
    expect(screen.getByLabelText('Hasło do konta')).toHaveValue('');
  });
});

describe('StatusCard: Wake-on-LAN', () => {
  it('okno WoL ma nazwę serwera, a potwierdzenie wywołuje akcję wake', async () => {
    const user = userEvent.setup();
    action.mockResolvedValue({ ok: true, message: 'Wysłano magic packet.' });
    await show({ state: 'OFFLINE', icmp_ok: false, tcp_ok: false });
    await user.click(wake());
    expect(screen.getByRole('dialog')).toHaveAccessibleName('Włączyć Serwer główny?');
    await user.click(screen.getByRole('button', { name: 'Wyślij WoL' }));
    await waitFor(() => expect(action).toHaveBeenCalledWith('/api/actions/wake', undefined));
  });
});