> **⚠️ DEPRECATED**: This file is a reference sample only. The authoritative design direction document is [`DESIGN-DIRECTION.md`](../../DESIGN-DIRECTION.md). All future design decisions should reference that document.

# Design System Document

## 1. Overview & Creative North Star: "The Celestial Storybook"

This design system is a departure from the cold, clinical nature of modern SaaS. Inspired by the evocative world-building of *Monument Valley* and the emotional intimacy of *Florence*, our Creative North Star is **"The Celestial Storybook."** 

We aim to create a digital environment that feels like an enchanted, hand-crafted artifact. We break the "template" look through **intentional asymmetry**, where layouts mimic the organic flow of a nebula rather than a rigid grid. Overlapping elements, isometric depth, and high-contrast typography scales turn functional screens into narrative experiences. This system is tech-forward in its performance but indie-game in its soul—warm, mysterious, and deeply human.

---

## 2. Colors: Obsidian Voids & Stellar Glow

The palette is anchored in deep, dark expanses, punctuated by the vibrant energy of distant stars.

*   **Background & Surfaces:** The primary environment is `background` (#0c0e14). We treat the UI as a dark void where light (content) emerges.
*   **The Primary Glow:** `primary` (#ffe792) and `primary_container` (#ffd709) act as our "Warm Gold" sunlight. These are reserved for high-priority actions and moments of "discovery."
*   **Ethereal Highlights:** `tertiary` (#85fff2) provides the "Ethereal Teal" cooling effect, used for secondary data or interactive feedback.
*   **Emotional Accents:** `secondary` (#ffb4a6) and its variants provide the "Soft Coral" warmth, humanizing the experience.

### The "No-Line" Rule
**Explicit Instruction:** Traditional 1px solid borders are strictly prohibited for sectioning. Structural boundaries must be defined solely through background color shifts. For example, a `surface_container_low` card sitting on a `surface` background creates a natural edge. We do not "draw" boxes; we "layer" light.

### Surface Hierarchy & Nesting
Treat the UI as a series of physical layers—like stacked sheets of frosted glass. 
*   **Nesting:** Place a `surface_container_highest` element inside a `surface_container` to indicate focus. 
*   **The Glass & Gradient Rule:** Use Glassmorphism for floating panels. Combine `surface_variant` at 60% opacity with a `backdrop-blur` of 20px. 
*   **Signature Textures:** Apply a subtle noise/grain texture (3-5% opacity) over the `background` to eliminate "flat" digital blacks and evoke a storybook paper feel. Use linear gradients from `primary` to `primary_dim` on large CTAs to give them a glowing, 3D presence.

---

## 3. Typography: Friendly Precision

The typography system balances the whimsy of rounded forms with the legibility required for modern applications.

*   **Display & Headlines (Plus Jakarta Sans):** Our "voice." We use large scales (e.g., `display-lg` at 3.5rem) with tight letter-spacing to create an editorial, high-end feel. The rounded nature of Jakarta mirrors the `ROUND_FULL` architecture of the UI.
*   **Body & Labels (Manrope):** Our "function." Manrope is chosen for its exceptional legibility at small scales. It maintains the friendly, modern tone without sacrificing the user’s ability to process dense information.
*   **Hierarchy as Identity:** Use high contrast between `headline-lg` (warm and bold) and `body-md` (muted `on_surface_variant`). This creates a rhythm that feels like a well-paced storybook.

---

## 4. Elevation & Depth: Tonal Layering

In this system, depth is a function of light, not lines.

*   **The Layering Principle:** Stacking surface tokens is the only way to achieve hierarchy. An "inner" content area should use `surface_container_low`, while the "outer" wrapper uses `surface`. This creates a soft, natural lift.
*   **Ambient Shadows:** If an element must float (like a modal), use an ultra-diffused shadow. 
    *   *Spec:* `0 20px 40px rgba(0, 0, 0, 0.4)` blended with a subtle glow of the `surface_tint` at 5% opacity. Shadows should feel like ambient occlusion in a 3D space, not a drop shadow on a flat page.
*   **The "Ghost Border" Fallback:** For accessibility in form fields, use the `outline_variant` token at 15% opacity. Never use 100% opaque borders.
*   **Isometric Lean:** Use 5-degree isometric tilts on card containers (`surface_container_high`) for decorative or featured content to break the horizontal monotony.

---

## 5. Components: The Hand-Crafted Kit

### Buttons
*   **Primary:** `primary` background with `on_primary` text. Shape is always `ROUND_FULL`. Add a subtle inner-glow (white at 10% opacity) on the top edge to simulate a "3D orb."
*   **Secondary:** `surface_variant` with a "Ghost Border." 

### Cards
*   **Styling:** Cards should never have borders. Use `surface_container_highest` with `ROUND_LG` (2rem) or `ROUND_XL` (3rem) corners. 
*   **Interaction:** On hover, a card should not "pop" up; it should "glow." Transition the background toward the `primary_container` color at 10% opacity.

### Inputs
*   **Text Fields:** Use `surface_container_lowest` for the input well. The label (`label-md`) should float in `on_surface_variant`. 
*   **Error State:** Use `error` (#ff716c) only for the text and a subtle `error_container` glow. Do not turn the entire box red; it breaks the celestial harmony.

### Celestial Progress Indicators
Instead of standard loaders, use concentric circles in `tertiary` (#85fff2) that pulse with varying opacities, mimicking a star's twinkle.

---

## 6. Do's and Don'ts

### Do:
*   **Do** use the Spacing Scale `16` (5.5rem) to create massive "breathing room" between major sections.
*   **Do** overlap elements. Let a graphic from one section bleed into a `surface_container` of another.
*   **Do** use `ROUND_FULL` for all interactive triggers (chips, buttons, toggles).

### Don't:
*   **Don't** use pure black (#000000) for anything other than `surface_container_lowest`.
*   **Don't** use sharp 90-degree corners. Even "square" elements should use at least `ROUND_SM`.
*   **Don't** use divider lines. If content needs separation, use a Spacing Scale of `8` (2.75rem) or a shift from `surface` to `surface_container_low`.
*   **Don't** use standard "Material Design" blue for links. Use `tertiary` or `primary` to maintain the celestial palette.
