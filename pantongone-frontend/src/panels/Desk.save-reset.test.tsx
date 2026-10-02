// @vitest-environment jsdom
import {beforeEach,describe,it,expect,vi} from 'vitest'
import {render,screen,fireEvent,waitFor} from '@testing-library/react'
import {Desk} from './Desk'
import * as api from '@/lib/api'
import fixture from '@/test-fixtures/meta.json'
import {EVERY_KEY} from '@/lib/permissions'
vi.mock('@/lib/api',async()=>({...await vi.importActual<typeof api>('@/lib/api'),getCustomers:vi.fn().mockResolvedValue({rows:[]}),calculate:vi.fn(),saveQuotation:vi.fn(),quotationForm:vi.fn()}))
const meta=fixture as unknown as api.Meta
const session={token:'t',expires_at:9999999999,user:{id:1,email:'qa@test',full_name:'QA',permissions:EVERY_KEY}} as api.Session
beforeEach(()=>{localStorage.clear();vi.clearAllMocks();vi.spyOn(window,'alert').mockImplementation(()=>{});vi.spyOn(window,'scrollTo').mockImplementation(()=>{});vi.mocked(api.calculate).mockResolvedValue({display:{},formulas:{}} as Awaited<ReturnType<typeof api.calculate>>)})
// The suggest box's toggle button carries the same aria-label as its input.
const field=(label:string)=>screen.getAllByLabelText(label).find(el=>el.tagName==='INPUT') as HTMLInputElement
function prepare(){
 const view=render(<Desk meta={meta} session={session} onSignOut={()=>{}}/>);
 fireEvent.click(screen.getByText('2. คำนวณราคาจริง'));
 const inputs=view.container.querySelectorAll('.desk-card input');
 // Use labels in the actual form, not assumptions about ordering.
 const customer=field(meta.labels!.fields.customer);
 fireEvent.change(customer,{target:{value:'QA customer'}});
 const code=field(meta.labels!.fields.customer_code);
 fireEvent.change(code,{target:{value:'QA001'}});
 return {view,customer,code,inputs};
}
describe('saved pricing form',()=>{
 it('clears only after successful save and keeps latest edit action',async()=>{
 vi.mocked(api.saveQuotation).mockResolvedValue({quote_ref:'LOCAL-QA-1'} as Awaited<ReturnType<typeof api.saveQuotation>>);
 const {view,customer}=prepare();fireEvent.click(view.container.querySelector('.desk-pricing-bottom button:nth-child(2)')!);
 await waitFor(()=>expect(api.saveQuotation).toHaveBeenCalledTimes(1));await waitFor(()=>expect(customer.value).toBe(''));
 expect(screen.getByRole('button',{name:'แก้ไขรายการที่บันทึกล่าสุด'})).not.toBeDisabled();expect(localStorage.getItem('pantongone.draft')).toBeNull();
 });
 it('retains inputs on save failure',async()=>{
 vi.mocked(api.saveQuotation).mockRejectedValue(Error('QA failed'));
 const {view,customer}=prepare();fireEvent.click(view.container.querySelector('.desk-pricing-bottom button:nth-child(2)')!);
 await waitFor(()=>expect(api.saveQuotation).toHaveBeenCalledTimes(1));await waitFor(()=>expect(window.alert).toHaveBeenCalledWith('QA failed'));expect(customer.value).toBe('QA customer');
 });
})
