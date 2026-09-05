import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ReviewField, fieldKey, groupFields, updateField } from '../src/documents';
import type { Field } from '../src/types';

const sourceField: Field = {
  code: 'vin',
  label: 'VIN',
  value: 'TEST0000000000123',
  type: 'text',
  unit: '',
  group: 'vehicle',
  index: 0,
  page: 2,
  source: 'VIN: TEST0000000000123',
  method: 'text',
  warnings: [],
  manual: false,
  absent: false,
};
describe('Weryfikacja odczytu', () => {
  it('umożliwia przejście do strony rzeczywistego źródła', async () => {
    const onSource = vi.fn();
    render(
      <ReviewField
        field={sourceField}
        original={sourceField}
        onChange={vi.fn()}
        onSource={onSource}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: 'Źródło · str. 2' }));
    expect(onSource).toHaveBeenCalledOnce();
  });
  it('korekta ręczna nie udaje wartości z fragmentu źródłowego', () => {
    render(
      <ReviewField
        field={{ ...sourceField, value: 'TEST0000000000999' }}
        original={sourceField}
        onChange={vi.fn()}
        onSource={vi.fn()}
      />,
    );
    expect(screen.getByText('Korekta ręczna')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Źródło/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/VIN: TEST/)).not.toBeInTheDocument();
  });
  it('brak w dokumencie jest jawnym nullem i osobnym znacznikiem', async () => {
    const onChange = vi.fn();
    render(<ReviewField field={sourceField} onChange={onChange} onSource={vi.fn()} />);
    await userEvent.click(screen.getByLabelText('Brak w dokumencie'));
    expect(onChange).toHaveBeenCalledWith({ absent: true, value: null });
  });
  it('puste nieoznaczone pole jest widoczne i dostępne', () => {
    render(
      <ReviewField
        field={{ ...sourceField, value: null, page: null, source: '' }}
        onChange={vi.fn()}
        onSource={vi.fn()}
      />,
    );
    expect(screen.getByText('Puste pole')).toBeInTheDocument();
    expect(screen.getByLabelText('VIN')).toHaveValue('');
    expect(screen.getByText('Bez wskazanego źródła')).toBeInTheDocument();
  });
  it('odrębnie zachowuje powtarzających się uczestników i nie zmienia wyniku źródłowego', () => {
    const first = {
      ...sourceField,
      group: 'participants',
      code: 'name',
      index: 0,
      value: 'DANE TESTOWE Osoba A',
    };
    const second = { ...first, index: 1, value: 'DANE TESTOWE Osoba B' };
    const fields = [first, second];
    const changed = updateField(fields, fieldKey(second), { value: 'DANE TESTOWE Korekta B' });
    expect(changed[0]).toBe(first);
    expect(changed[1]?.value).toBe('DANE TESTOWE Korekta B');
    expect(second.value).toBe('DANE TESTOWE Osoba B');
    expect(groupFields(changed)[0]?.[1]).toHaveLength(2);
  });
  it('pokazuje polskie etykiety ról, zachowując wartości API', async () => {
    const onChange = vi.fn();
    render(
      <ReviewField
        field={{ ...sourceField, code: 'role', label: 'Rola', value: 'insured' }}
        onChange={onChange}
        onSource={vi.fn()}
      />,
    );
    expect(screen.getByLabelText('Rola')).toHaveValue('insured');
    await userEvent.selectOptions(screen.getByLabelText('Rola'), 'policyholder');
    expect(onChange).toHaveBeenCalledWith({ value: 'policyholder', absent: false });
  });
});
