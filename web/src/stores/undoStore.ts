import { create } from "zustand";

/** Undo/Redo 操作类型 */
export type UndoActionType =
  | "CREATE_GROUP" | "DELETE_GROUP" | "MOVE_ELEMENT"
  | "MODIFY_ATTRIBUTE" | "CHANGE_PAGE_TYPE" | "CHANGE_LAYOUT_TYPE"
  | "CHANGE_SKU_TYPE" | "MERGE_GROUPS" | "DRAG_TO_GROUP";

export interface UndoAction {
  type: UndoActionType;
  description: string;
  forward: () => void;
  backward: () => void;
}

interface UndoState {
  undoStack: UndoAction[];
  redoStack: UndoAction[];
  canUndo: boolean;
  canRedo: boolean;
  push: (action: UndoAction) => void;
  undo: () => void;
  redo: () => void;
  clear: () => void;
}

const MAX_STACK = 30;

export const useUndoStore = create<UndoState>((set, get) => ({
  undoStack: [],
  redoStack: [],
  canUndo: false,
  canRedo: false,

  push: (action) =>
    set((s) => {
      const stack = [...s.undoStack, action];
      if (stack.length > MAX_STACK) stack.shift();
      return { undoStack: stack, redoStack: [], canUndo: true, canRedo: false };
    }),

  undo: () => {
    const { undoStack, redoStack } = get();
    if (undoStack.length === 0) return;
    const action = undoStack[undoStack.length - 1];
    action.backward();
    set({
      undoStack: undoStack.slice(0, -1),
      redoStack: [...redoStack, action],
      canUndo: undoStack.length > 1,
      canRedo: true,
    });
  },

  redo: () => {
    const { undoStack, redoStack } = get();
    if (redoStack.length === 0) return;
    const action = redoStack[redoStack.length - 1];
    action.forward();
    set({
      undoStack: [...undoStack, action],
      redoStack: redoStack.slice(0, -1),
      canUndo: true,
      canRedo: redoStack.length > 1,
    });
  },

  clear: () =>
    set({ undoStack: [], redoStack: [], canUndo: false, canRedo: false }),
}));
