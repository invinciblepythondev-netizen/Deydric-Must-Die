Phase 1: Core Models (2-3 hours)

  Build thin Python wrappers for existing stored procedures:

  1. models/character.py - Character operations
  2. models/location.py - Location operations
  3. models/turn.py - Turn history operations
  4. models/wound.py - Wound tracking
  5. models/relationship.py - Relationships

  These are trivial - just wrap procedure calls like you did for GameTime and SceneMood.

  Phase 2: Action Execution (3-4 hours)

  Build the action executor and supporting services:

  1. services/action_executor.py - Execute action sequences
  2. services/turn_order.py - Manage turn order
  3. services/witness_tracker.py - Determine who sees actions

  Phase 3: Game Engine (2-3 hours)

  Build the orchestrator:

  1. services/game_engine.py - Main game loop
    - start_new_game()
    - process_turn()
    - process_character_turn()

  Phase 4: Flask App (3 hours)

  1. app.py - Flask entry point
  2. routes/game.py - Game routes

  Phase 5: UI Templates (3-4 hours)

  1. templates/base.html
  2. templates/game.html
  3. templates/components/action_options.html

  Phase 6: Seed Data (1 hour)

  1. scripts/seed_data.py - Create test game content

  💡 Before You Start UI Planning

  The UI considerations document is ready, but you can't implement UI yet because:

  1. ❌ No way to create a game (GameEngine.start_new_game() doesn't exist)
  2. ❌ No way to execute actions (ActionExecutor doesn't exist)
  3. ❌ No Flask routes to call from UI
  4. ❌ No test data to render

  Recommendation: Follow the phases above in order. Once GameEngine works, UI is straightforward.

  📋 Quick Start Checklist

  □ Phase 1: Build Character, Location, Turn models (wrappers only)
  □ Phase 2: Build ActionExecutor service
  □ Phase 3: Build GameEngine orchestrator
  □ Test: Can run a game loop headlessly (no UI)
  □ Phase 4: Build Flask app + routes
  □ Phase 5: Build UI templates (refer to UI_CONSIDERATIONS.md)
  □ Phase 6: Seed test data
  □ Test: Can play through browser

  The good news: Your foundation is excellent. You just need the integration layer, and then UI falls into place. The UI_CONSIDERATIONS.md has
  everything you need for when you reach that phase!