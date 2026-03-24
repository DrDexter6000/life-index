> **⚠️ DEPRECATED**: This file is a reference sample only. The authoritative design direction document is [`DESIGN-DIRECTION.md`](../DESIGN-DIRECTION.md). All future design decisions should reference that document.

# Design System: Celestial Editorial

## 1. Overview & Creative North Star: "The Ethereal Archivist"

This design system moves beyond the cold, utilitarian nature of standard AI interfaces to embrace the warmth of a digital heirloom. Our Creative North Star is **"The Ethereal Archivist"**—a concept that treats every interaction as a moment of literary reflection. 

To break the "template" look, we reject the rigid grid in favor of **intentional asymmetry** and **overlapping depth**. Components should feel like they are floating in a vast, starlit nebula, rather than being locked into a spreadsheet. By utilizing high-contrast typography scales (pairing an expansive serif with a compact sans-serif) and organic, full-rounded forms, we create a space that feels both technologically advanced and intimately handwritten.

---

## 2. Colors & Tonal Depth

The palette is anchored in a deep, sophisticated "Ink-Space" foundation, punctuated by the glowing warmth of celestial bodies.

### The Foundation
*   **Background (#0A0E14):** Our canvas. A deep, cyan-tinted black that provides infinite depth.
*   **Surface Tiers:** Use `surface-container-lowest` (#000000) for the deepest background elements and `surface-bright` (#262C36) for active, elevated components.

### The Accents (Light & Life)
*   **Primary (#FFE792):** A glowing amber. Reserved for the "heartbeat" of the UI—primary actions and active states.
*   **Secondary (#F9873E):** A soft orange. Used for secondary highlights and interactive moments that require warmth.
*   **Tertiary (#F9F9FF):** A creamy white. Used for high-readability text and subtle icons to maintain an editorial feel.

### Critical Rules for Visual Sophistication
*   **The "No-Line" Rule:** 1px solid borders are strictly prohibited for sectioning. Boundaries must be defined solely through background color shifts. For example, a `surface-container-low` section should sit on a `surface` background to create a soft transition.
*   **The Glass & Gradient Rule:** Floating elements (modals, tooltips, navigation) must use **Glassmorphism**. Apply a semi-transparent `surface` color with a `backdrop-blur` (e.g., 12px-20px) to allow the "nebula" background to bleed through.
*   **Signature Textures:** Use subtle linear gradients for CTAs, transitioning from `primary` (#FFE792) to `primary-container` (#FFD709) at a 135-degree angle to provide "visual soul."

---

### 3. Typography: The Literary Voice

The typography system is a dialogue between the classic (The Journal) and the modern (The Agent).

*   **Display & Headlines (Newsreader):** Use the elegant Serif for all headlines. The dramatic scale difference between `display-lg` (3.5rem) and `body-lg` (1rem) creates an editorial, high-end feel. These should feel like titles in a premium storybook.
*   **Body & Labels (Manrope):** A clean, humanist sans-serif. It provides a technical, "AI-native" clarity that balances the romanticism of the headers.
*   **Hierarchy Note:** Always lead with Serif for storytelling and transition to Sans-Serif for functional data and input.

---

### 4. Elevation & Depth: Tonal Layering

We do not use shadows to simulate height; we use **Tonal Layering** and light.

*   **The Layering Principle:** Depth is achieved by "stacking" surface tokens. Place a `surface-container-highest` card atop a `surface-container-low` background. This creates a soft, natural lift reminiscent of stacked sheets of fine vellum.
*   **Ambient Glows:** When a floating effect is required, shadows must be extra-diffused. Use a 40px blur at 6% opacity, tinted with `primary` (#FFE792) rather than grey. This mimics the ambient light of a nearby star.
*   **The "Ghost Border" Fallback:** If a container needs more definition, use a `outline-variant` (#44484F) at **15% opacity**. This creates a "breath" of a line rather than a hard edge.

---

### 5. Components

#### Buttons
*   **Primary:** `ROUND_FULL` (9999px), `primary` background with `on-primary` text. Apply a subtle outer glow (4px blur) using the `primary` color to simulate "digital warmth."
*   **Secondary:** `ROUND_FULL`, `surface-bright` background with a "Ghost Border."

#### Cards & Lists
*   **Strict Rule:** No dividers. Use vertical white space (`spacing-6` or `spacing-8`) to separate list items.
*   **Shape:** All cards must use `rounded-xl` (3rem) or `rounded-full` to maintain the organic, hand-drawn feel.

#### Input Fields
*   **Style:** Minimalist. No bottom border. Use a `surface-container-lowest` pill shape with `rounded-full`. 
*   **Active State:** Instead of a thick border, use a soft glow (nebula effect) that emanates from behind the input field using `secondary_dim`.

#### Celestial Progress Indicators
*   Replace standard loading bars with "Orbitals"—a central glowing dot (`primary`) with a rotating ring (`secondary`) to lean into the storybook theme.

---

### 6. Do's and Don'ts

**Do:**
*   **Embrace Asymmetry:** Offset images and text blocks. Let the UI breathe with generous, uneven padding.
*   **Use Nebula Glows:** Place large, low-opacity radial gradients (amber and navy) in the background of screens to create "digital warmth."
*   **Prioritize Readability:** Ensure `on-surface` text remains high-contrast against the deep background.

**Don't:**
*   **No Hard Edges:** Avoid `rounded-none` or `rounded-sm`. Everything should feel soft and organic.
*   **No Pure Greys:** Never use `#808080`. All neutrals must be tinted with navy (`surface-variant`) or amber (`on-surface-variant`).
*   **No Grid-Lock:** Don't align every element to a rigid 12-column grid. Let elements overlap slightly to create a layered, "collage" effect common in high-end journals.

---

*Director's Final Note: The system should feel like it was grown, not built. Every interaction should whisper, never shout.*