## UI Considerations for Prototype

## Overview

This document outlines UI/UX considerations for the game prototype, covering information architecture, interaction patterns, and technical implementation approaches.

---

## Core UI Requirements

### What the Player Needs to See

1. **Game State Context** (Always visible)
   - Current turn number
   - Current time (Day X, HH:MM AM/PM, time of day category)
   - Current location name
   - Weather/lighting (from time tracking)

2. **Character State** (Always visible)
   - Character name
   - Current emotional state
   - Wounds (summary: "Healthy" or "Wounded: X injuries")
   - Status effects ("Intoxicated", "Frightened", etc.)
   - Inventory (expandable)

3. **Current Scene** (Main focus area)
   - Location description (full text)
   - General mood description
   - Present characters (names, appearance, stance)
   - Recent turn history (last 5-10 turns, scrollable)

4. **Action Selection** (During player's turn)
   - 4-6 action options with:
     - Option number
     - Summary (1 sentence)
     - Full action sequence (expandable)
     - Emotional tone badge
     - Escalation indicator (⚠️ escalates / ✓ de-escalates)

5. **Turn Execution Feedback** (After selection)
   - Action execution animation/sequence
   - Outcome descriptions
   - Mood changes
   - Relationship changes

---

## Information Architecture

### Page Structure

```
┌──────────────────────────────────────────────────────────────┐
│ Header (Game Context)                                        │
│  Turn 15 | Day 1, 9:30 PM (dusk) | The Rusty Flagon        │
└──────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────┐
│ Sidebar (Character State)                                    │
│                                                              │
│  [Character Avatar/Portrait]                                 │
│  Aldric the Barkeep                                          │
│  Wary and suspicious                                         │
│                                                              │
│  Health: Healthy                                             │
│  Status: [Slightly Anxious]                                  │
│                                                              │
│  Inventory (3)                                               │
│    - Bar rag                                                 │
│    - Keys to tavern                                          │
│    - Concealed cudgel                                        │
│                                                              │
│  Relationships                                               │
│    - Gareth: ⚠️ Fearful (40%)                                │
│    - Mira: ✓ Trusting (70%)                                  │
└──────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────┐
│ Main Content Area                                            │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Location: The Rusty Flagon Tavern                      │ │
│  │ A dimly lit tavern with rough wooden tables...         │ │
│  │                                                         │ │
│  │ Mood: Moderately tense. The situation is escalating.  │ │
│  │                                                         │ │
│  │ Present:                                               │ │
│  │  • Gareth (sitting aggressively, drunk)               │ │
│  │  • Mira (watching nervously)                           │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Recent Events                         [Scroll to view]  │ │
│  │                                                         │ │
│  │ Turn 14: Gareth (speak)                                │ │
│  │   "Shut up with that noise!"                           │ │
│  │                                                         │ │
│  │ Turn 15: Aldric (speak)                                │ │
│  │   "Gareth, I'm asking you nicely..."                   │ │
│  │                                                         │ │
│  │ Turn 16: Gareth (emote)                                │ │
│  │   Laughs mockingly and continues drinking              │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ YOUR TURN - Choose an Action                           │ │
│  │                                                         │ │
│  │  1. Confront Gareth with force         [⚠️ Escalates] │ │
│  │     Aggressive | Reach for cudgel and demand he leave │ │
│  │     [View full sequence]                               │ │
│  │                                                         │ │
│  │  2. Offer free drink to calm situation [✓ De-escalates]│ │
│  │     Conciliatory | Pour ale, suggest peace            │ │
│  │     [View full sequence]                               │ │
│  │                                                         │ │
│  │  3. Signal bouncer for help            [Neutral]       │ │
│  │     Tactical | Subtly call for backup                 │ │
│  │     [View full sequence]                               │ │
│  │                                                         │ │
│  │  ... (2-3 more options)                                │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## UI Components Detail

### 1. Action Option Card

Each action option should display:

```html
<div class="action-option" data-option-id="1">
  <div class="option-header">
    <span class="option-number">1</span>
    <h3 class="option-summary">Confront Gareth with force</h3>
    <span class="escalation-badge escalate">⚠️ Escalates</span>
  </div>

  <div class="option-meta">
    <span class="emotional-tone">Aggressive</span>
    <span class="mood-impact">Tension +30, Hostility +25</span>
  </div>

  <div class="option-preview">
    Quick: Reach for cudgel, demand he leave, step forward menacingly
  </div>

  <details class="option-details">
    <summary>View full action sequence (4 actions)</summary>
    <ol class="action-sequence">
      <li class="action private">
        <span class="action-type">think</span>
        <span class="action-desc">Gareth is going to cause a fight. I need to act.</span>
      </li>
      <li class="action public">
        <span class="action-type">emote</span>
        <span class="action-desc">Reaches under bar for cudgel</span>
      </li>
      <li class="action public">
        <span class="action-type">speak</span>
        <span class="action-desc">"Gareth, I'm asking you once more. Leave. Now."</span>
      </li>
      <li class="action public">
        <span class="action-type">emote</span>
        <span class="action-desc">Steps around bar, cudgel visible</span>
      </li>
    </ol>
  </details>

  <button class="select-action-btn" data-option-id="1">
    Choose this action
  </button>
</div>
```

### 2. Turn History Feed

```html
<div class="turn-history">
  <h3>Recent Events</h3>

  <!-- Turn 14 -->
  <div class="turn-entry">
    <div class="turn-header">
      <span class="turn-number">Turn 14</span>
      <span class="turn-time">9:24 PM</span>
    </div>

    <!-- Character A's actions (sequence) -->
    <div class="character-turn">
      <span class="character-name">Gareth</span>
      <span class="character-stance">sitting aggressively</span>

      <div class="action-sequence">
        <!-- Private thought - only if this is player's character -->
        <div class="action private" title="Only you know this">
          <span class="icon">🔒</span>
          <em>I've had enough of that bard...</em>
        </div>

        <!-- Public speech -->
        <div class="action public speak">
          <span class="icon">💬</span>
          "Shut up with that noise!"
        </div>

        <!-- Public emote -->
        <div class="action public emote">
          <span class="icon">👤</span>
          Slams fist on table
        </div>
      </div>

      <!-- Mood impact indicator -->
      <div class="mood-change">
        Tension increased slightly
      </div>
    </div>
  </div>

  <!-- Turn 15 -->
  <div class="turn-entry">
    <!-- ... similar structure ... -->
  </div>
</div>
```

### 3. Character Sidebar Card

```html
<aside class="character-sidebar">
  <div class="character-card">
    <div class="character-portrait">
      <img src="/static/portraits/aldric.png" alt="Aldric">
    </div>

    <h2 class="character-name">Aldric the Barkeep</h2>

    <div class="character-emotional-state">
      <label>Emotional State:</label>
      <span class="state-value wary">Wary and suspicious</span>
    </div>

    <div class="character-health">
      <label>Health:</label>
      <span class="health-status healthy">Healthy</span>
      <!-- OR if wounded: -->
      <!-- <span class="health-status wounded">Wounded</span>
           <ul class="wound-list">
             <li class="wound moderate">Moderate cut on left arm</li>
           </ul> -->
    </div>

    <div class="character-status-effects">
      <label>Status:</label>
      <span class="status-badge anxiety">Slightly Anxious</span>
    </div>

    <details class="character-inventory">
      <summary>Inventory (3)</summary>
      <ul>
        <li>Bar rag</li>
        <li>Keys to tavern</li>
        <li>Concealed cudgel</li>
      </ul>
    </details>

    <details class="character-relationships">
      <summary>Relationships</summary>
      <ul>
        <li class="relationship">
          <span class="rel-character">Gareth</span>
          <span class="rel-indicator fear">⚠️ Fearful</span>
          <span class="rel-value">40%</span>
        </li>
        <li class="relationship">
          <span class="rel-character">Mira</span>
          <span class="rel-indicator trust">✓ Trusting</span>
          <span class="rel-value">70%</span>
        </li>
      </ul>
    </details>
  </div>
</aside>
```

### 4. Location Scene

```html
<div class="location-scene">
  <div class="location-header">
    <h2 class="location-name">The Rusty Flagon Tavern</h2>
    <div class="location-meta">
      <span class="time-of-day dusk">🌆 Dusk</span>
      <span class="lighting">Dimly lit, shadows lengthening</span>
    </div>
  </div>

  <p class="location-description">
    A dimly lit tavern with rough wooden tables and mismatched chairs.
    The air is thick with the smell of ale, smoke, and sawdust. A
    crackling fireplace provides the only real light, casting long
    shadows across the worn floorboards.
  </p>

  <div class="scene-mood">
    <strong>Mood:</strong>
    <span class="mood-description tense">
      Moderately tense. The situation is escalating. There is underlying antagonism.
    </span>
  </div>

  <div class="present-characters">
    <h3>Present Characters</h3>
    <ul>
      <li class="character-present">
        <strong>Gareth the Mercenary</strong>
        <span class="character-desc">
          Tall, scarred man in leather armor, sitting aggressively at the bar.
          Travel-worn gear, hand near sword.
        </span>
      </li>
      <li class="character-present">
        <strong>Mira the Bard</strong>
        <span class="character-desc">
          Young woman with bright eyes, watching nervously from corner booth.
          Colorful performer's clothes, lute beside her.
        </span>
      </li>
    </ul>
  </div>
</div>
```

---

## Interaction Patterns

### Player Turn Flow

```
1. Player sees "YOUR TURN" notification
   ↓
2. Action options appear (4-6 cards)
   ↓
3. Player can:
   - Read option summaries
   - Expand to see full action sequences
   - Hover to see mood impact
   ↓
4. Player clicks "Choose this action"
   ↓
5. Confirmation modal (optional):
   "Are you sure? This will escalate tension."
   ↓
6. Loading indicator while executing
   ↓
7. Action sequence plays out (animated or step-by-step reveal)
   ↓
8. Outcome displayed
   ↓
9. Turn passes to next character (AI takes turn automatically)
   ↓
10. When back to player, repeat from step 1
```

### AI Turn Display

```
1. Turn header updates: "Gareth's turn"
   ↓
2. Brief pause (0.5-1s for dramatic effect)
   ↓
3. AI's action sequence appears in turn history feed
   ↓
4. Each action reveals sequentially (think → speak → emote → act)
   ↓
5. Mood/relationship changes animate
   ↓
6. Brief pause, then next character
```

---

## Visual Design Considerations

### Color Coding

**Mood Indicators:**
- 🟢 **De-escalation**: Green, calming colors
- 🟡 **Neutral**: Yellow/gray, no change
- 🟠 **Escalation**: Orange/red, warning colors

**Relationships:**
- 💚 **High trust** (70-100%): Green
- 🧡 **Moderate trust** (30-70%): Orange
- ❤️ **Low trust** (0-30%): Red
- 🖤 **Negative trust** (-100-0%): Dark red

**Time of Day:**
- 🌅 **Dawn**: Purple/pink
- ☀️ **Morning**: Bright yellow
- 🌤️ **Afternoon**: Blue
- 🌇 **Evening**: Orange
- 🌆 **Dusk**: Purple
- 🌙 **Night**: Dark blue/black

**Action Types:**
- 💭 **Think** (private): Light gray, italic
- 💬 **Speak** (public): Speech bubble icon
- 👤 **Emote** (public): Person icon
- ⚔️ **Attack** (public): Sword icon
- 🤝 **Interact**: Handshake icon
- 👁️ **Examine**: Eye icon
- 🚶 **Move**: Footsteps icon

### Typography

- **Headings**: Bold serif font (Georgia, Merriweather)
- **Body text**: Clean sans-serif (Inter, Source Sans)
- **Character dialogue**: Serif or distinct font (Crimson Text)
- **UI elements**: Sans-serif (system font stack for performance)

### Layout

- **Desktop**: Sidebar + main content (shown above)
- **Tablet**: Collapsible sidebar, main content takes priority
- **Mobile**: Stack vertically, action options as swipeable cards

---

## Technical Implementation

### Frontend Stack Options

#### Option 1: Server-Rendered (Simple)
**Best for prototype**

- **Templates**: Jinja2 (Flask built-in)
- **Styling**: Plain CSS or Tailwind CSS
- **JavaScript**: Vanilla JS or Alpine.js (lightweight)
- **Forms**: Standard HTML forms with POST

**Pros:**
- Fast to build
- No build step
- Works without JavaScript
- Easy to debug

**Cons:**
- Full page reloads
- Less interactive
- No smooth animations

#### Option 2: HTMX (Recommended for MVP)
**Best balance for prototype**

- **Templates**: Jinja2
- **Styling**: Tailwind CSS
- **Interactivity**: HTMX (no JavaScript needed!)
- **Forms**: HTMX-powered partial updates

**Pros:**
- Partial page updates (no full reloads)
- Smooth interactions
- Minimal JavaScript
- Progressive enhancement

**Cons:**
- Slight learning curve
- Need to think about partial rendering

**Example:**
```html
<!-- Action selection with HTMX -->
<button
  hx-post="/game/{{ game_id }}/action"
  hx-vals='{"option_id": 1}'
  hx-target="#turn-result"
  hx-swap="outerHTML"
  class="select-action-btn"
>
  Choose this action
</button>

<!-- Turn result container -->
<div id="turn-result"></div>
```

#### Option 3: Single Page App (Overkill for prototype)
- React/Vue + Flask API
- Full client-side routing
- Complex state management

**Don't do this for prototype** - too much overhead.

### Recommended Prototype Stack

```
Backend:
  - Flask
  - SQLAlchemy (thin wrappers over stored procedures)
  - Jinja2 templates

Frontend:
  - HTMX for interactivity
  - Tailwind CSS for styling
  - Alpine.js for small bits of client-side logic (optional)
  - Minimal vanilla JavaScript

No build step needed!
```

---

## State Management

### Session vs Database

**Store in Flask session:**
- Current player character ID
- Last viewed game ID
- UI preferences (collapsed sidebars, etc.)

**Store in database:**
- Everything else (game state, characters, actions, etc.)

**Don't store in memory:**
- Game state (use database always)

### Real-Time Updates (Future)

For prototype: **Poll or manual refresh**.

For production:
- WebSockets (Flask-SocketIO)
- Server-Sent Events (SSE)

---

## Accessibility

### Must-Haves

1. **Semantic HTML**
   - Proper heading hierarchy
   - ARIA labels where needed
   - Form labels

2. **Keyboard Navigation**
   - All interactive elements tabbable
   - Clear focus indicators
   - Keyboard shortcuts (1-6 for action selection)

3. **Screen Reader Support**
   - ARIA live regions for turn updates
   - Descriptive button text
   - Alt text for icons/images

4. **Color Contrast**
   - WCAG AA compliant (4.5:1 for text)
   - Don't rely solely on color (use icons + text)

---

## Performance Considerations

### Loading Strategy

1. **Initial Page Load**
   - Load critical CSS inline
   - Defer non-critical JavaScript
   - Compress images

2. **Subsequent Actions**
   - HTMX handles partial updates
   - Only re-render changed sections

3. **Long Turn History**
   - Pagination or virtual scrolling
   - Load last 10 turns by default
   - "Load more" button for older turns

### Image Strategy

- **Character portraits**: Lazy load, compressed (WebP)
- **Icons**: SVG sprites or icon font
- **Background images**: CSS, compressed

---

## Mobile Considerations

### Touch Targets

- Minimum 44x44px tap targets
- Adequate spacing between options
- Swipe gestures for navigating history

### Responsive Breakpoints

```css
/* Mobile first */
.action-option { /* Base styles */ }

/* Tablet */
@media (min-width: 768px) {
  .action-option { /* Wider layout */ }
}

/* Desktop */
@media (min-width: 1024px) {
  .action-option { /* Sidebar visible */ }
}
```

### Mobile-Specific Features

- Pull to refresh game state
- Swipe between turns in history
- Bottom navigation (if multi-page)
- Floating action button for quick actions

---

## Prototype UI Checklist

### Must Have (Phase 1)
- [ ] Game header (turn, time, location)
- [ ] Location scene description
- [ ] Turn history feed (last 10 turns)
- [ ] Action option cards (4-6 options)
- [ ] Action selection buttons
- [ ] Basic character sidebar

### Should Have (Phase 2)
- [ ] Expandable action sequences
- [ ] Mood indicator
- [ ] Escalation badges
- [ ] Present characters list
- [ ] Loading states

### Nice to Have (Phase 3)
- [ ] Character portraits
- [ ] Animated turn transitions
- [ ] Relationship visualizations
- [ ] Inventory management UI
- [ ] Character sheet modal

### Can Wait (Post-Prototype)
- [ ] Combat animations
- [ ] Map/navigation UI
- [ ] Advanced filtering/search
- [ ] Multiple save slots UI
- [ ] Settings panel

---

## Example Wireframe (ASCII)

```
┌─────────────────────────────────────────────────────────────────────┐
│ ⚔️ DEYDRIC MUST DIE                        Turn 15 | Day 1, 9:30 PM│
│                                             🌆 The Rusty Flagon     │
└─────────────────────────────────────────────────────────────────────┘
┌──────────┬─────────────────────────────────────────────────────────┐
│          │  Location: The Rusty Flagon Tavern                     │
│ ALDRIC   │  A dimly lit tavern with rough wooden tables...        │
│          │                                                         │
│ [Avatar] │  Mood: Moderately tense ⚠️                              │
│          │                                                         │
│ 💭 Wary  │  Present: Gareth 👤 (aggressive), Mira 👤 (nervous)    │
│          ├─────────────────────────────────────────────────────────┤
│ ❤️ Health│  Recent Events                              [Scroll ▼] │
│ Healthy  │                                                         │
│          │  [Turn 14] Gareth slams table: "Shut up!"              │
│ 🎒 Items │  [Turn 15] You warn Gareth to calm down                │
│ • Cudgel │  [Turn 16] Gareth laughs mockingly                     │
│ • Keys   ├─────────────────────────────────────────────────────────┤
│          │  ⭐ YOUR TURN - Choose an Action                        │
│ 🤝 Rels  │                                                         │
│ Gareth   │  ┌──────────────────────────────────────────────────┐ │
│ ⚠️ 40%   │  │ 1. Confront with force          [⚠️ Escalates]  │ │
│          │  │    Aggressive • Reach for cudgel...              │ │
│ Mira     │  │    [View sequence] [CHOOSE THIS]                 │ │
│ ✓ 70%    │  └──────────────────────────────────────────────────┘ │
│          │                                                         │
│          │  ┌──────────────────────────────────────────────────┐ │
│          │  │ 2. Offer free drink           [✓ De-escalates]  │ │
│          │  │    Conciliatory • Pour ale, suggest peace       │ │
│          │  │    [View sequence] [CHOOSE THIS]                 │ │
│          │  └──────────────────────────────────────────────────┘ │
│          │                                                         │
│          │  ┌──────────────────────────────────────────────────┐ │
│          │  │ 3. Signal bouncer               [Neutral]        │ │
│          │  │    Tactical • Subtly call for backup            │ │
│          │  │    [View sequence] [CHOOSE THIS]                 │ │
│          │  └──────────────────────────────────────────────────┘ │
└──────────┴─────────────────────────────────────────────────────────┘
```

---

## Next Steps

1. **Build Flask app.py** with basic routes
2. **Create base.html template** with layout
3. **Create game.html template** with structure shown above
4. **Add Tailwind CSS** for rapid styling
5. **Integrate HTMX** for interactivity
6. **Test with seeded data**

---

## Resources

**Design Inspiration:**
- AI Dungeon (text adventure UI)
- Disco Elysium (choice presentation)
- Fallen London (narrative presentation)
- Twine games (simple but effective)

**Technical:**
- HTMX: https://htmx.org
- Tailwind CSS: https://tailwindcss.com
- Alpine.js: https://alpinejs.dev

**Accessibility:**
- WCAG Guidelines: https://www.w3.org/WAI/WCAG21/quickref/
- A11y Project: https://www.a11yproject.com
