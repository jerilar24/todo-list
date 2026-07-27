import { useEffect } from "react";
import "./Modal.css";

function Modal({ title, children, onClose }) {
    useEffect(() => {
        function closeOnEscape(event) {
            if (event.key === "Escape") onClose();
        }
        document.addEventListener("keydown", closeOnEscape);
        return () => document.removeEventListener("keydown", closeOnEscape);
    }, [onClose]);

    return (
        <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
            <div
                className="modal"
                role="dialog"
                aria-modal="true"
                aria-labelledby="modal-title"
                onMouseDown={(event) => event.stopPropagation()}
            >
                <h2 id="modal-title">{title}</h2>
                {children}
            </div>
        </div>
    );
}

export default Modal;
