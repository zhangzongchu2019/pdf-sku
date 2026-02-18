import { describe, it, expect, beforeEach } from "vitest";
import { useAnnotationStore } from "../../src/stores/annotationStore";

describe("annotationStore", () => {
  beforeEach(() => {
    useAnnotationStore.getState().reset();
  });

  it("starts with empty state", () => {
    const s = useAnnotationStore.getState();
    expect(s.elements).toHaveLength(0);
    expect(s.groups).toHaveLength(0);
    expect(s.selectedElementIds).toHaveLength(0);
  });

  it("sets and clears annotations", () => {
    const { addAnnotation } = useAnnotationStore.getState();
    addAnnotation({ type: "test", field: "x", value: "y" });
    expect(useAnnotationStore.getState().annotations).toHaveLength(1);

    useAnnotationStore.getState().removeAnnotation(0);
    expect(useAnnotationStore.getState().annotations).toHaveLength(0);
  });

  it("selects a SKU", () => {
    const { selectSku } = useAnnotationStore.getState();
    selectSku("sku-123");
    expect(useAnnotationStore.getState().selectedSkuId).toBe("sku-123");

    selectSku(null);
    expect(useAnnotationStore.getState().selectedSkuId).toBeNull();
  });

  it("creates a group from element IDs", () => {
    const { createGroup } = useAnnotationStore.getState();
    createGroup(["e1", "e2"]);
    const { groups } = useAnnotationStore.getState();
    expect(groups.length).toBe(1);
    expect(groups[0].elementIds).toContain("e1");
    expect(groups[0].elementIds).toContain("e2");
  });

  it("deletes a group", () => {
    const { createGroup } = useAnnotationStore.getState();
    createGroup(["e1"]);
    const { groups, deleteGroup } = useAnnotationStore.getState();
    expect(groups.length).toBe(1);

    deleteGroup(groups[0].id);
    expect(useAnnotationStore.getState().groups.length).toBe(0);
  });

  it("updates SKU attribute on group", () => {
    const { createGroup } = useAnnotationStore.getState();
    createGroup(["e1"]);
    const groupId = useAnnotationStore.getState().groups[0].id;

    useAnnotationStore.getState().updateSKUAttribute(groupId, "name", "Test Product");
    const g = useAnnotationStore.getState().groups.find((g) => g.id === groupId);
    expect(g?.skuAttributes.name).toBe("Test Product");
  });

  it("sets tool mode", () => {
    const { setTool } = useAnnotationStore.getState();
    setTool("lasso");
    expect(useAnnotationStore.getState().activeToolMode).toBe("lasso");

    setTool("select");
    expect(useAnnotationStore.getState().activeToolMode).toBe("select");
  });

  it("reset clears all state", () => {
    const s = useAnnotationStore.getState();
    s.addAnnotation({ type: "test" });
    s.createGroup(["e1"]);

    useAnnotationStore.getState().reset();
    const after = useAnnotationStore.getState();
    expect(after.elements).toHaveLength(0);
    expect(after.groups).toHaveLength(0);
    expect(after.annotations).toHaveLength(0);
  });
});
