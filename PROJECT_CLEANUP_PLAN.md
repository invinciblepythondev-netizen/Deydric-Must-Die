# Project Cleanup Plan

## Current Bloat Analysis

**Total Files:**
- 102 Python files
- 63 Markdown files (36 in root directory alone!)
- 53 SQL files
- 66 scripts in `/scripts/`
- 16 database migrations

**Directory Sizes:**
- `services/`: 964KB
- `scripts/`: 506KB
- `database/`: 360KB
- `models/`: 232KB

---

## Category 1: Scripts Bloat (66 files, ~506KB)

### 🗑️ DELETE - Test Scripts (Can be recreated if needed)
These are one-off test scripts with no ongoing value:

```bash
# Delete these (20+ files):
rm scripts/test_action_generation.py          # 20K - superseded by actual tests
rm scripts/test_all_apis.py                    # 3.3K
rm scripts/test_atmospheric_json.py            # 3.3K
rm scripts/test_chroma.py                      # 1.9K
rm scripts/test_connections.py                 # 7.6K
rm scripts/test_context_management.py          # 11K
rm scripts/test_integration_simple.py          # 11K
rm scripts/test_item_search.py                 # 1.9K
rm scripts/test_objective_system.py            # 11K
rm scripts/test_phase1_together_ai.py          # 4.3K
rm scripts/test_phase2_manual_fallback.py      # 8.8K
rm scripts/test_phase3_prompt_templates.py     # 8.6K
rm scripts/test_phase4_llm_service.py          # 5.7K
rm scripts/test_phase5_objective_planner.py    # 4.4K
rm scripts/test_phase6_comprehensive.py        # 9.0K
rm scripts/test_provider_chain.py              # 5.6K
rm scripts/test_providers.py                   # 6.7K
rm scripts/test_qdrant.py                      # 6.6K
rm scripts/test_resilient_fallback.py          # 5.5K
rm scripts/test_route.py                       # 1.8K
rm scripts/test_semantic_search.py             # 2.4K
rm scripts/test_situational_context.py         # 12K
rm scripts/test_summary_generation.py          # 6.0K
rm scripts/test_time_tracking.py               # 12K
```

**Savings: ~164KB, 24 files**

### 📦 ARCHIVE - One-Time Migration Scripts (After migrations are applied)
Create `scripts/archive/migrations/` and move:

```bash
mkdir -p scripts/archive/migrations
mv scripts/apply_appearance_state_migration.py scripts/archive/migrations/
mv scripts/apply_memory_summary_migration.py scripts/archive/migrations/
mv scripts/apply_summary_embedding_migration.py scripts/archive/migrations/
mv scripts/apply_turn_duration_migration.py scripts/archive/migrations/
mv scripts/backfill_memory_summaries.py scripts/archive/migrations/
mv scripts/backfill_summary_embeddings.py scripts/archive/migrations/
mv scripts/migrate_location_id_to_string.py scripts/archive/migrations/
mv scripts/migrate_objectives.py scripts/archive/migrations/
mv scripts/update_character_procedures.py scripts/archive/migrations/
mv scripts/update_memory_summary_procedures.py scripts/archive/migrations/
mv scripts/update_turn_procedures.py scripts/archive/migrations/
mv scripts/update_turn_witnessed_procedure.py scripts/archive/migrations/
```

**Savings: ~38KB out of main scripts, 12 files**

### 📦 ARCHIVE - Setup/Seed Scripts (Used during initial development)
Create `scripts/archive/setup/` and move:

```bash
mkdir -p scripts/archive/setup
mv scripts/analyze_character_personalities.py scripts/archive/setup/
mv scripts/assign_character_traits.py scripts/archive/setup/
mv scripts/create_initial_game.py scripts/archive/setup/
mv scripts/create_mood_table.py scripts/archive/setup/
mv scripts/generate_objectives_for_test_chars.py scripts/archive/setup/
mv scripts/generate_secret_key.py scripts/archive/setup/
mv scripts/import_characters_json.py scripts/archive/setup/
mv scripts/import_locations_json.py scripts/archive/setup/
mv scripts/init_recurring_templates.py scripts/archive/setup/
mv scripts/init_recurring_templates_standalone.py scripts/archive/setup/
mv scripts/populate_character_items.py scripts/archive/setup/
mv scripts/populate_content_settings.py scripts/archive/setup/
mv scripts/populate_west_guest_room_items.py scripts/archive/setup/
mv scripts/seed_cognitive_traits.py scripts/archive/setup/
mv scripts/seed_cognitive_traits_standalone.py scripts/archive/setup/
mv scripts/setup_content_settings.py scripts/archive/setup/
mv scripts/setup_seduction_scenario.py scripts/archive/setup/
```

**Savings: ~141KB out of main scripts, 17 files**

### ✅ KEEP - Essential Operational Scripts
These should stay in main `/scripts/`:

```
scripts/init_db.py                      # Database initialization
scripts/migrate_db.py                   # Migration runner
scripts/reset_db.py                     # Database reset
scripts/check_characters.py             # Quick checks
scripts/check_context_sizes.py          # Context monitoring
scripts/check_images.py                 # Image verification
scripts/check_qdrant_items.py           # Qdrant verification
scripts/create_qdrant_indexes.py        # Index management
scripts/fix_location_id_index.py        # Index fixes
scripts/list_characters.py              # Character listing
scripts/verify_character_items.py       # Item verification
scripts/verify_game_state.py            # Game state checks
scripts/verify_location_search.py       # Search verification
```

**Keep: ~50KB, 13 files**

### Summary: Scripts Cleanup
- **Delete**: 164KB, 24 files (test scripts)
- **Archive**: 179KB, 29 files (migrations + setup)
- **Keep**: 50KB, 13 files (operational)
- **Total savings**: 343KB moved/deleted, keep only 13 essential scripts

---

## Category 2: Documentation Bloat (36 root-level MD files)

### 🗑️ DELETE - Outdated Status/Completion Files

```bash
rm FLASK_SETUP_COMPLETE.md
rm LOCATION_IMPORT_COMPLETE.md
rm PHASE_1_COMPLETE.md
rm PROTOTYPE_SETUP_STATUS.md
rm PROTOTYPE_STATUS_UPDATE.md
```

### 📦 CONSOLIDATE - Integration Guides (Too many overlapping guides)

**Keep ONE comprehensive guide, archive the rest:**

```bash
# Keep the most comprehensive:
# ARCHITECTURE.md - Main technical doc
# CLAUDE.md - Development guide

# Move to docs/archive/:
mkdir -p docs/archive
mv LLM_INTEGRATION_GUIDE.md docs/archive/
mv LLM_INTEGRATION_PLAN.md docs/archive/
mv PROTOTYPE_NEXT_STEPS.md docs/archive/
mv PROTOTYPE_SETUP_GUIDE.md docs/archive/
mv CHARACTER_JSON_INTEGRATION_SUMMARY.md docs/archive/
```

### 📁 ORGANIZE - Feature Documentation

Create organized documentation structure:

```bash
# Create structure
mkdir -p docs/systems
mkdir -p docs/guides
mkdir -p docs/technical

# Move to organized locations:
mv ACTION_GENERATION_GUIDE.md docs/systems/
mv CHARACTER_IMAGE_SYSTEM.md docs/systems/
mv CHARACTER_STATUS_GUIDE.md docs/systems/
mv CONTEXT_GUIDE.md docs/systems/
mv EMOTIONAL_STATE_SYSTEM.md docs/systems/
mv ITEM_SYSTEM_DESIGN.md docs/systems/
mv ITEM_SYSTEM_GUIDE.md docs/systems/
mv MULTI_TURN_ACTIONS_DESIGN.md docs/systems/
mv OBJECTIVE_SYSTEM_DESIGN.md docs/systems/
mv TIME_TRACKING_GUIDE.md docs/systems/

mv CHARACTER_JSON_IMPORT_GUIDE.md docs/guides/
mv LOCATION_JSON_IMPORT_GUIDE.md docs/guides/
mv PROVIDER_FALLBACK_GUIDE.md docs/guides/
mv AIMLAPI_SETUP.md docs/guides/
mv SETUP.md docs/guides/

mv DYNAMIC_CLOTHING_AND_ITEM_CHANGES.md docs/technical/
mv GAME_LOOP_ANALYSIS.md docs/technical/
mv MULTI_TURN_OPTIONS_COMPARISON.md docs/technical/
mv OBJECTIVE_SYSTEM_INTEGRATION.md docs/technical/
mv QDRANT_API_UPDATE.md docs/technical/
mv QDRANT_MIGRATION.md docs/technical/
mv UI_CONSIDERATIONS.md docs/technical/
```

### ✅ KEEP in Root - Essential Documentation

```
README.md                               # Project overview
ARCHITECTURE.md                         # Technical architecture
CLAUDE.md                               # Development guide for Claude Code
OBJECTIVE_SYSTEM_QUICK_REFERENCE.md    # Quick reference for active system
```

### Summary: Documentation Cleanup
- **Delete**: 5 outdated status files
- **Archive**: 5 old integration guides
- **Organize**: 26 files into structured docs/ directory
- **Keep in root**: 4 essential files

---

## Category 3: Database Migrations (16 files)

### ✅ KEEP ALL - But Document Status

Migrations should NEVER be deleted, but we should document which are applied:

```bash
# Create migration status file
cat > database/migrations/APPLIED_MIGRATIONS.md << 'EOF'
# Applied Migrations

## Production Applied
- 010_add_turn_duration_tracking.sql ✅ Applied
- 011_add_tiered_memory_summaries.sql ✅ Applied
- 012_add_summary_embeddings.sql ✅ Applied
- 013_add_appearance_state_columns.sql ✅ Applied

## Notes
- Never delete migration files
- Mark new migrations as applied in this file
- Migrations are tracked in schema_migration table
EOF
```

---

## Category 4: Untracked Files (Git Status)

### Organize Into Logical Commits

**Commit 1: Item System**
```bash
git add services/item_action_parser.py
git add services/item_context_helper.py
git add services/item_generator.py
git add services/item_store.py
git add ITEM_SYSTEM_DESIGN.md
git add ITEM_SYSTEM_GUIDE.md
git commit -m "Add item system with Qdrant integration and dynamic clothing

- ItemStore: Qdrant-based item storage with semantic search
- ItemContextHelper: Dynamic clothing from worn items, LLM-driven item updates
- ItemGenerator: LLM-powered item generation
- ItemActionParser: Parse item-related actions"
```

**Commit 2: Dynamic Clothing & Item Changes**
```bash
git add services/context_manager.py
git add services/action_generator.py
git add routes/game.py
git add DYNAMIC_CLOTHING_AND_ITEM_CHANGES.md
git commit -m "Implement dynamic clothing from Qdrant and LLM-driven item updates

- Context manager now pulls clothing from worn items
- Action generator uses Qdrant for character clothing
- Item properties update based on atmospheric descriptions
- Fixes for location_id indexing in Qdrant"
```

**Commit 3: Qdrant Fixes**
```bash
git add services/vector_store.py
git add scripts/fix_location_id_index.py
git add scripts/migrate_location_id_to_string.py
git add QDRANT_API_UPDATE.md
git commit -m "Fix Qdrant API compatibility and location_id indexing

- Update search() to query_points() for new Qdrant API
- Fix location_id to use keyword index instead of integer
- Migrate existing data to string location_id values"
```

**Commit 4: Database Migrations**
```bash
git add database/migrations/010_add_turn_duration_tracking.sql
git add database/migrations/011_add_tiered_memory_summaries.sql
git add database/migrations/012_add_summary_embeddings.sql
git add database/migrations/013_add_appearance_state_columns.sql
git add database/procedures/memory_summary_procedures.sql
git commit -m "Add database migrations for turn duration, memory summaries, and appearance state

- Turn duration tracking for multi-turn actions
- Tiered memory summary system with embeddings
- Character appearance state columns (detailed/summary)"
```

**Commit 5: Verification & Test Scripts**
```bash
git add scripts/check_qdrant_items.py
git add scripts/create_qdrant_indexes.py
git add scripts/verify_character_items.py
git add scripts/verify_location_search.py
git add scripts/test_item_search.py
git add scripts/test_semantic_search.py
git commit -m "Add verification and test scripts for item system and Qdrant"
```

**Commit 6: Migration Application Scripts**
```bash
# Only if you want to keep these in version control
# Otherwise archive them as shown above
```

---

## Cleanup Script

Here's a complete cleanup script:

```bash
#!/bin/bash
# cleanup.sh - Execute all cleanup operations

set -e

echo "🧹 Starting Project Cleanup..."
echo ""

# 1. DELETE TEST SCRIPTS
echo "📝 Deleting test scripts..."
rm -f scripts/test_*.py
echo "   ✓ Deleted 24 test scripts"

# 2. ARCHIVE MIGRATIONS
echo "📦 Archiving migration scripts..."
mkdir -p scripts/archive/migrations
mv scripts/apply_*.py scripts/archive/migrations/ 2>/dev/null || true
mv scripts/backfill_*.py scripts/archive/migrations/ 2>/dev/null || true
mv scripts/migrate_*.py scripts/archive/migrations/ 2>/dev/null || true
mv scripts/update_*_procedures.py scripts/archive/migrations/ 2>/dev/null || true
echo "   ✓ Archived 12 migration scripts"

# 3. ARCHIVE SETUP SCRIPTS
echo "📦 Archiving setup scripts..."
mkdir -p scripts/archive/setup
mv scripts/analyze_*.py scripts/archive/setup/ 2>/dev/null || true
mv scripts/assign_*.py scripts/archive/setup/ 2>/dev/null || true
mv scripts/create_initial_*.py scripts/archive/setup/ 2>/dev/null || true
mv scripts/create_mood_*.py scripts/archive/setup/ 2>/dev/null || true
mv scripts/generate_*.py scripts/archive/setup/ 2>/dev/null || true
mv scripts/import_*.py scripts/archive/setup/ 2>/dev/null || true
mv scripts/init_recurring_*.py scripts/archive/setup/ 2>/dev/null || true
mv scripts/populate_*.py scripts/archive/setup/ 2>/dev/null || true
mv scripts/seed_*.py scripts/archive/setup/ 2>/dev/null || true
mv scripts/setup_*.py scripts/archive/setup/ 2>/dev/null || true
echo "   ✓ Archived 17 setup scripts"

# 4. ORGANIZE DOCUMENTATION
echo "📚 Organizing documentation..."
mkdir -p docs/{systems,guides,technical,archive}

# Delete outdated status files
rm -f FLASK_SETUP_COMPLETE.md LOCATION_IMPORT_COMPLETE.md
rm -f PHASE_1_COMPLETE.md PROTOTYPE_SETUP_STATUS.md PROTOTYPE_STATUS_UPDATE.md
echo "   ✓ Deleted 5 outdated status files"

# Move to organized locations
mv ACTION_GENERATION_GUIDE.md docs/systems/ 2>/dev/null || true
mv CHARACTER_IMAGE_SYSTEM.md docs/systems/ 2>/dev/null || true
mv CHARACTER_STATUS_GUIDE.md docs/systems/ 2>/dev/null || true
mv CONTEXT_GUIDE.md docs/systems/ 2>/dev/null || true
mv EMOTIONAL_STATE_SYSTEM.md docs/systems/ 2>/dev/null || true
mv ITEM_SYSTEM_DESIGN.md docs/systems/ 2>/dev/null || true
mv ITEM_SYSTEM_GUIDE.md docs/systems/ 2>/dev/null || true
mv MULTI_TURN_ACTIONS_DESIGN.md docs/systems/ 2>/dev/null || true
mv OBJECTIVE_SYSTEM_DESIGN.md docs/systems/ 2>/dev/null || true
mv TIME_TRACKING_GUIDE.md docs/systems/ 2>/dev/null || true

mv CHARACTER_JSON_IMPORT_GUIDE.md docs/guides/ 2>/dev/null || true
mv LOCATION_JSON_IMPORT_GUIDE.md docs/guides/ 2>/dev/null || true
mv PROVIDER_FALLBACK_GUIDE.md docs/guides/ 2>/dev/null || true
mv AIMLAPI_SETUP.md docs/guides/ 2>/dev/null || true
mv SETUP.md docs/guides/ 2>/dev/null || true

mv DYNAMIC_CLOTHING_AND_ITEM_CHANGES.md docs/technical/ 2>/dev/null || true
mv GAME_LOOP_ANALYSIS.md docs/technical/ 2>/dev/null || true
mv MULTI_TURN_OPTIONS_COMPARISON.md docs/technical/ 2>/dev/null || true
mv OBJECTIVE_SYSTEM_INTEGRATION.md docs/technical/ 2>/dev/null || true
mv QDRANT_API_UPDATE.md docs/technical/ 2>/dev/null || true
mv QDRANT_MIGRATION.md docs/technical/ 2>/dev/null || true
mv UI_CONSIDERATIONS.md docs/technical/ 2>/dev/null || true

mv LLM_INTEGRATION_GUIDE.md docs/archive/ 2>/dev/null || true
mv LLM_INTEGRATION_PLAN.md docs/archive/ 2>/dev/null || true
mv PROTOTYPE_NEXT_STEPS.md docs/archive/ 2>/dev/null || true
mv PROTOTYPE_SETUP_GUIDE.md docs/archive/ 2>/dev/null || true
mv CHARACTER_JSON_INTEGRATION_SUMMARY.md docs/archive/ 2>/dev/null || true

echo "   ✓ Organized 31 documentation files"

# 5. CREATE MIGRATION STATUS
echo "📋 Creating migration status file..."
cat > database/migrations/APPLIED_MIGRATIONS.md << 'EOF'
# Applied Migrations

## Applied to Production
- 010_add_turn_duration_tracking.sql ✅
- 011_add_tiered_memory_summaries.sql ✅
- 012_add_summary_embeddings.sql ✅
- 013_add_appearance_state_columns.sql ✅

## Notes
- Never delete migration files
- Mark new migrations as applied in this file
- Migrations are tracked in schema_migration table
EOF
echo "   ✓ Created migration status file"

echo ""
echo "✨ Cleanup Complete!"
echo ""
echo "Summary:"
echo "  - Deleted: 24 test scripts (~164KB)"
echo "  - Archived: 29 migration/setup scripts (~179KB)"
echo "  - Organized: 31 documentation files"
echo "  - Remaining in /scripts/: 13 essential operational scripts"
echo "  - Remaining in root: 4 essential documentation files"
echo ""
echo "Next steps:"
echo "  1. Review archived files in scripts/archive/"
echo "  2. Check docs/ directory structure"
echo "  3. Commit organized files to git"
```

---

## Recommended File Structure After Cleanup

```
Deydric Must Die/
├── README.md                    # Project overview
├── ARCHITECTURE.md              # Technical architecture
├── CLAUDE.md                    # Development guide
├── OBJECTIVE_SYSTEM_QUICK_REFERENCE.md
│
├── docs/
│   ├── systems/                 # System documentation (10 files)
│   ├── guides/                  # User/setup guides (5 files)
│   ├── technical/               # Technical notes (7 files)
│   └── archive/                 # Old docs (5 files)
│
├── scripts/
│   ├── init_db.py              # Keep: Essential operations
│   ├── migrate_db.py           # Keep: Essential operations
│   ├── reset_db.py             # Keep: Essential operations
│   ├── check_*.py              # Keep: 5 verification scripts
│   ├── verify_*.py             # Keep: 3 verification scripts
│   ├── list_*.py               # Keep: 1 utility script
│   ├── create_qdrant_indexes.py # Keep: Index management
│   ├── fix_location_id_index.py # Keep: Index fixes
│   │
│   └── archive/
│       ├── migrations/         # 12 applied migration scripts
│       └── setup/              # 17 one-time setup scripts
│
├── database/
│   ├── migrations/             # 16 SQL migration files (keep all)
│   │   └── APPLIED_MIGRATIONS.md
│   ├── procedures/             # SQL procedures
│   └── schemas/                # SQL schemas
│
├── services/                   # 15-20 core service files
├── models/                     # 8-10 model files
├── routes/                     # 3-5 route files
└── templates/                  # HTML templates
```

---

## Expected Impact

**Before Cleanup:**
- Root directory: 36 MD files
- Scripts: 66 Python files (506KB)
- Difficult to navigate
- Unclear what's active vs deprecated

**After Cleanup:**
- Root directory: 4 essential MD files
- Scripts: 13 operational files (~50KB active)
- Clear organization by purpose
- Easy to find current documentation

**Total Space Savings:**
- Scripts: ~450KB moved to archive or deleted
- Documentation: Better organized (minimal space savings but huge usability improvement)

---

## Maintenance Going Forward

### Rules for New Files:

1. **Scripts:**
   - Test scripts: Use proper `tests/` directory or delete after use
   - Migration scripts: Move to `scripts/archive/migrations/` after applying
   - Setup scripts: Move to `scripts/archive/setup/` if one-time use

2. **Documentation:**
   - System docs → `docs/systems/`
   - User guides → `docs/guides/`
   - Technical notes → `docs/technical/`
   - Outdated → `docs/archive/` (never delete, might have historical value)
   - Only 4 files allowed in root: README, ARCHITECTURE, CLAUDE, and one quick reference

3. **Migrations:**
   - Always keep in `database/migrations/`
   - Update `APPLIED_MIGRATIONS.md` when applied
   - Never delete, even if very old

### Monthly Cleanup Checklist:
- [ ] Review `scripts/` for test scripts to delete
- [ ] Move one-time migration scripts to archive
- [ ] Check for root-level documentation to organize
- [ ] Update `APPLIED_MIGRATIONS.md` with new migrations
- [ ] Review `scripts/archive/` and delete if truly obsolete (>6 months)
