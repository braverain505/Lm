import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LandingProductSlider } from "./landing-product-slider";

/**
 * The complaint this guards against was simply that the screens sat still, so
 * the timer is the feature. Fake timers let the rotation be asserted without
 * waiting for it, and the caption is unique per screen — the screens themselves
 * all stay mounted behind the cross-fade, so their text can't be used to tell
 * which one is on top.
 */

/** A little past the rotation delay, whatever it is set to. */
const ADVANCE_MS = 6000;

const captionOf = (snippet: RegExp) => screen.queryByText(snippet);

describe("LandingProductSlider rotation", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const advance = () =>
    act(() => {
      vi.advanceTimersByTime(ADVANCE_MS);
    });

  it("moves to the next screen on its own", () => {
    render(<LandingProductSlider />);
    expect(captionOf(/One dashboard for the term/i)).toBeInTheDocument();

    advance();

    expect(captionOf(/One dashboard for the term/i)).not.toBeInTheDocument();
    expect(captionOf(/Teachers enter marks for their own classes/i)).toBeInTheDocument();
  });

  it("still rotates for someone who asked their OS for reduced motion", () => {
    // Rotation used to be switched off outright for this preference, which is
    // how the hero ended up frozen on screen one. Only the movement is dropped
    // now, so the screens still change.
    const original = window.matchMedia;
    window.matchMedia = ((query: string) => ({
      matches: query.includes("prefers-reduced-motion"),
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    })) as unknown as typeof window.matchMedia;

    try {
      render(<LandingProductSlider />);
      advance();
      expect(captionOf(/Teachers enter marks for their own classes/i)).toBeInTheDocument();
    } finally {
      window.matchMedia = original;
    }
  });

  it("keeps going through the rest of the screens", () => {
    render(<LandingProductSlider />);

    advance();
    advance();

    expect(captionOf(/Fee structures, invoices, payments/i)).toBeInTheDocument();
  });

  it("stops while paused and picks up again when resumed", () => {
    render(<LandingProductSlider />);

    fireEvent.click(screen.getByRole("button", { name: /pause the rotating screens/i }));
    advance();
    advance();
    expect(captionOf(/One dashboard for the term/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /resume the rotating screens/i }));
    advance();
    expect(captionOf(/One dashboard for the term/i)).not.toBeInTheDocument();
    expect(captionOf(/Teachers enter marks for their own classes/i)).toBeInTheDocument();
  });

  it("lets a chosen screen be picked without the rotation stealing it back", () => {
    render(<LandingProductSlider />);

    fireEvent.click(screen.getByRole("button", { name: /show Clearis AI/i }));
    expect(captionOf(/answer built from real rows/i)).toBeInTheDocument();

    // Half a rotation later the choice is still on screen…
    act(() => {
      vi.advanceTimersByTime(ADVANCE_MS / 2);
    });
    expect(captionOf(/answer built from real rows/i)).toBeInTheDocument();

    // …and only moves on once its full turn has elapsed.
    advance();
    expect(captionOf(/One dashboard for the term/i)).toBeInTheDocument();
  });
});
