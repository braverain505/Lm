// Registers @testing-library/jest-dom matchers (toBeInTheDocument, toBeDisabled…)
// and their types with Vitest's expect.
import "@testing-library/jest-dom/vitest";

// @dnd-kit measures droppable/draggable nodes with ResizeObserver, which jsdom
// does not implement. A no-op stub lets the designer mount without crashing —
// these tests exercise the click surfaces, not live drag measurement.
if (!("ResizeObserver" in globalThis)) {
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  (globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = ResizeObserverStub;
}
