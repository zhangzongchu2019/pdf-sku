import { useEffect } from "react";

type KeyCombo = { key: string; ctrl?: boolean; shift?: boolean; alt?: boolean };

export function useKeyboard(combos: Array<KeyCombo & { handler: () => void }>) {
  useEffect(() => {
    const listener = (e: KeyboardEvent) => {
      for (const combo of combos) {
        if (
          e.key === combo.key &&
          !!e.ctrlKey === !!combo.ctrl &&
          !!e.shiftKey === !!combo.shift &&
          !!e.altKey === !!combo.alt
        ) {
          e.preventDefault();
          combo.handler();
          return;
        }
      }
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, [combos]);
}
