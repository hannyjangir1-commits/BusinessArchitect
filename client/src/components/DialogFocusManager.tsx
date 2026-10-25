import { useEffect } from 'react';

/** Keep keyboard focus in the topmost visible modal and return it on close. */
export function DialogFocusManager() {
  useEffect(() => {
    let current: HTMLElement | null = null;
    let previous: HTMLElement | null = null;
    const focusable = (root: HTMLElement) => Array.from(root.querySelectorAll<HTMLElement>(
      'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex="0"]'
    )).filter(element => element.getClientRects().length > 0);
    const findDialog = () => {
      const dialogs = Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"], .modal-card'));
      const next = dialogs.filter(element => element.getClientRects().length > 0).at(-1) || null;
      if (next === current) return;
      if (!next) {
        if (previous?.isConnected) previous.focus();
        previous = null;
      } else {
        if (!current) previous = document.activeElement as HTMLElement;
        next.setAttribute('role', 'dialog');
        next.setAttribute('aria-modal', 'true');
        if (!next.hasAttribute('aria-label') && !next.hasAttribute('aria-labelledby')) {
          const heading = next.querySelector('h2,h3,h4');
          if (heading?.textContent) next.setAttribute('aria-label', heading.textContent);
        }
        if (!next.contains(document.activeElement)) (focusable(next)[0] || next).focus();
      }
      current = next;
    };
    const onKey = (event: KeyboardEvent) => {
      // If a managed Dialog with its own stack is active, defer to it to prevent competing traps
      if (document.querySelector('[role="dialog"][data-managed-dialog="true"]') || !current || event.key !== 'Tab') return;
      const controls = focusable(current);
      if (!controls.length) { event.preventDefault(); current.tabIndex = -1; current.focus(); return; }
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && (document.activeElement === first || !current.contains(document.activeElement))) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !current.contains(document.activeElement))) {
        event.preventDefault(); first.focus();
      }
    };
    const observer = new MutationObserver(findDialog);
    observer.observe(document.body, { childList: true, subtree: true });
    document.addEventListener('keydown', onKey);
    findDialog();
    return () => { observer.disconnect(); document.removeEventListener('keydown', onKey); };
  }, []);
  return null;
}
