// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Suggest, type Suggestion } from './Suggest'

/* THE LIST MUST OPEN FOR A FINGER, NOT ONLY FOR A KEYBOARD.
 *
 * ArrowDown-to-browse serves a desk; the factory floor works a touch screen,
 * where an autocomplete that opens only on typing is a box people type full
 * company names into - four spellings of one customer later, the history is
 * quietly split (the exact disease Suggest exists to cure).
 */

const rows: Suggestion[] = [
  { customer: 'Honda Automobile (Thailand) Co.,Ltd', customer_code: 'HND-01', times: 210 },
  { customer: 'Daikin Industries (Thailand) Ltd.', customer_code: '', times: 180 },
  { customer: 'Nippon Honda Parts Co.,Ltd.', customer_code: '', times: 40 },
]

function draw(onChange = vi.fn(), onPick = vi.fn()) {
  render(
    <Suggest label="ชื่อลูกค้า" value="" onChange={onChange} onPick={onPick} rows={rows} />,
  )
  return { onChange, onPick }
}

describe('picking an existing customer', () => {
  it('a click on the empty box opens the most-quoted list', async () => {
    draw()
    await userEvent.click(screen.getByRole('combobox', { name: 'ชื่อลูกค้า' }))
    expect(screen.getByRole('listbox')).toBeTruthy()
    const options = screen.getAllByRole('option')
    expect(options[0]?.textContent).toContain('Honda Automobile')
    expect(options).toHaveLength(3)
  })

  it('the ▾ toggle opens and closes the list without typing', () => {
    draw()
    const toggle = screen.getByRole('button', { name: 'ชื่อลูกค้า' })
    fireEvent.mouseDown(toggle)
    expect(screen.getByRole('listbox')).toBeTruthy()
    fireEvent.mouseDown(toggle)
    expect(screen.queryByRole('listbox')).toBeNull()
  })

  it('choosing a row fills the name and brings its code along', () => {
    const { onChange, onPick } = draw()
    fireEvent.mouseDown(screen.getByRole('button', { name: 'ชื่อลูกค้า' }))
    fireEvent.mouseDown(screen.getByRole('option', { name: /Honda Automobile/ }))
    expect(onChange).toHaveBeenCalledWith('Honda Automobile (Thailand) Co.,Ltd')
    expect(onPick).toHaveBeenCalledWith('HND-01')
  })

  it('a customer with no code never writes a blank over the code box', () => {
    const { onPick } = draw()
    fireEvent.mouseDown(screen.getByRole('button', { name: 'ชื่อลูกค้า' }))
    fireEvent.mouseDown(screen.getByRole('option', { name: /Daikin/ }))
    expect(onPick).not.toHaveBeenCalled()
  })
})
