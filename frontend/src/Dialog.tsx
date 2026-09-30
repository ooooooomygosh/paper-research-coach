import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import "./onboarding.css";

/** The browser's top layer provides inert background and native focus containment. */
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
    <dialog ref={ref} className="prc-dialog" aria-label={label}
      onCancel={(e) => { e.preventDefault(); if (canClose) onClose(); }}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.preventDefault(); e.stopPropagation(); if (canClose) onClose();
        }
      }}>
      {children}
    </dialog>, document.body,
  );
}
