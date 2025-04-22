import { ReactNode, useEffect } from "react";
import { createPortal } from "react-dom";
import clsx from "clsx";

interface ModalProps {
  isOpen: boolean;
  title?: string;
  onClose: () => void;
  children: ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
  closable?: boolean;
}

export default function Modal({
  isOpen,
  title,
  onClose,
  children,
  size = "md",
  closable = true,
}: ModalProps) {
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape" && closable) onClose();
    };
    document.addEventListener("keydown", handleEsc);
    return () => document.removeEventListener("keydown", handleEsc);
  }, [closable]);

  if (!isOpen) return null;

  const sizeClass = {
    sm: "max-w-sm",
    md: "max-w-md",
    lg: "max-w-3xl",
    xl: "max-w-5xl",
  }[size];

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div
        className={clsx(
          "bg-white rounded-xl shadow-lg w-full",
          sizeClass,
          "max-h-[90vh] overflow-auto animate-fadeIn"
        )}
      >
        {title && (
          <div className="border-b px-6 py-4 flex justify-between items-center">
            <h2 className="text-lg font-semibold text-gray-800">{title}</h2>
            {closable && (
              <button
                onClick={onClose}
                className="text-gray-500 hover:text-red-600 transition"
                aria-label="Close"
              >
                ✕
              </button>
            )}
          </div>
        )}
        <div className="p-6">{children}</div>
      </div>
    </div>,
    document.body
  );
}
