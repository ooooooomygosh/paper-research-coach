import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import "./onboarding.css";

function tabStops(dialog: HTMLDialogElement): HTMLElement[] {
  return Array.from(dialog.querySelectorAll<HTMLElement>(
    "button, [href], input, select, textarea, summary, [tabindex]",
  )).filter((element) => {
    const implicitSummary = element.matches("summary") && !element.hasAttribute("tabindex");
    if ((!implicitSummary && element.tabIndex < 0) || element.matches(":disabled") ||
        element.closest("[hidden], [inert]") || !element.getClientRects().length ||
        getComputedStyle(element).visibility === "hidden") return false;
    // Collapsed details can retain layout boxes in Chromium; rects alone are insufficient.
    for (let parent = element.parentElement; parent && parent !== dialog; parent = parent.parentElement) {
      if (parent.matches("details:not([open])")) {
        const summary = parent.querySelector(":scope > summary");
        if (!summary?.contains(element)) return false;
      }
    }
    return true;
  });
}

/** Native top layer makes the background inert; explicit Tab wrapping retains focus. */
export default function Dialog({ label, onClose, children, canClose = true }: {
  label: string;
  onClose: () => void;
  children: ReactNode;
  canClose?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const dialog = ref.current!;
    dialog.showModal();
    return () => {
      dialog.close();
      if (opener?.isConnected) opener.focus();
    };
  }, []);
  return createPortal(
    <dialog ref={ref} className="prc-dialog" aria-label={label} tabIndex={-1}
      onCancel={(e) => { e.preventDefault(); if (canClose) onClose(); }}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.preventDefault(); e.stopPropagation(); if (canClose) onClose();
        }
        if (e.key === "Tab") {
          const dialog = e.currentTarget;
          const controls = tabStops(dialog);
          const first = controls[0], last = controls.at(-1);
          if (!first) { e.preventDefault(); dialog.focus(); }
          else if (e.shiftKey && (document.activeElement === first || document.activeElement === dialog)) {
            e.preventDefault(); last?.focus();
          } else if (!e.shiftKey && (document.activeElement === last || document.activeElement === dialog)) {
            e.preventDefault(); first.focus();
          }
        }
      }}>
      {children}
    </dialog>, document.body,
  );
}
