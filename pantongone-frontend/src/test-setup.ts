import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

/* WITHOUT THIS, EVERY TEST AFTER THE FIRST SEES TWO SCREENS.
 *
 * Testing Library unmounts what it rendered in an afterEach it registers
 * ITSELF - but only when vitest is running with globals on, which this project
 * is not (each test file imports describe and it by name, so that a reader can
 * see where they come from). Without globals nothing registers the hook, the
 * previous render stays in the document, and the next query finds two of
 * everything. The error it prints - "found multiple elements" - reads like a
 * fault in the screen, which is the worst kind of false alarm: it sends
 * somebody looking for a duplicate label that does not exist.
 */
afterEach(cleanup)

/* Matchers that say what went wrong in words: "expected the element to be
 * disabled" rather than "expected false to be true". Harmless in the node
 * environment, where no test uses them. */
import '@testing-library/jest-dom/vitest'

/* jsdom 30 still ships <dialog> without showModal or close, so anything drawn
 * with Confirm or Dialog throws the moment it opens.
 *
 * This shim moves the `open` attribute and fires the close event, which is
 * enough to drive the flow: press the button, tick the reasons, save. It is NOT
 * the real thing - the focus trap, ::backdrop and Escape all come from the
 * browser and none of them exists here. Those are the reason the app uses a
 * native <dialog> in the first place, so they are worth remembering as untested
 * rather than assumed. */
/* jsdom has no layout, so it has no scrollIntoView either - and LinkField calls
 * it on every keystroke to keep the highlighted option in view. Without this,
 * the first search result THROWS inside the effect and React unmounts the
 * picker: the whole screen comes down and the test reports the missing element
 * rather than the missing method. Scrolling is a browser matter (rule F11);
 * this only stops its absence taking the tree with it. */
if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function scrollIntoView() {}
}

if (typeof HTMLDialogElement !== 'undefined' && !HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function showModal() {
    this.open = true
  }
  HTMLDialogElement.prototype.show = function show() {
    this.open = true
  }
  HTMLDialogElement.prototype.close = function close(returnValue?: string) {
    this.open = false
    if (returnValue !== undefined) this.returnValue = returnValue
    this.dispatchEvent(new Event('close'))
  }
}
