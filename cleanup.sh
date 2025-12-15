#!/bin/bash
# cleanup.sh - Execute all cleanup operations

set -e

echo "🧹 Starting Project Cleanup..."
echo ""

# 1. DELETE TEST SCRIPTS
echo "📝 Deleting test scripts..."
rm -f scripts/test_*.py
echo "   ✓ Deleted test scripts"

# 2. ARCHIVE MIGRATIONS
echo "📦 Archiving migration scripts..."
mkdir -p scripts/archive/migrations
mv scripts/apply_*.py scripts/archive/migrations/ 2>/dev/null || true
mv scripts/backfill_*.py scripts/archive/migrations/ 2>/dev/null || true
mv scripts/migrate_location_id_to_string.py scripts/archive/migrations/ 2>/dev/null || true
mv scripts/migrate_objectives.py scripts/archive/migrations/ 2>/dev/null || true
mv scripts/update_*_procedures.py scripts/archive/migrations/ 2>/dev/null || true
echo "   ✓ Archived migration scripts"

# 3. ARCHIVE SETUP SCRIPTS
echo "📦 Archiving setup scripts..."
mkdir -p scripts/archive/setup
mv scripts/analyze_*.py scripts/archive/setup/ 2>/dev/null || true
mv scripts/assign_*.py scripts/archive/setup/ 2>/dev/null || true
mv scripts/create_initial_*.py scripts/archive/setup/ 2>/dev/null || true
mv scripts/create_mood_*.py scripts/archive/setup/ 2>/dev/null || true
mv scripts/generate_secret_key.py scripts/archive/setup/ 2>/dev/null || true
mv scripts/generate_objectives_for_test_chars.py scripts/archive/setup/ 2>/dev/null || true
mv scripts/import_*.py scripts/archive/setup/ 2>/dev/null || true
mv scripts/init_recurring_*.py scripts/archive/setup/ 2>/dev/null || true
mv scripts/populate_*.py scripts/archive/setup/ 2>/dev/null || true
mv scripts/seed_*.py scripts/archive/setup/ 2>/dev/null || true
mv scripts/setup_*.py scripts/archive/setup/ 2>/dev/null || true
echo "   ✓ Archived setup scripts"

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

echo "   ✓ Organized documentation files"

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
echo "  - Deleted: ~24 test scripts (~164KB)"
echo "  - Archived: ~29 migration/setup scripts (~179KB)"
echo "  - Organized: ~31 documentation files"
echo "  - Remaining in /scripts/: ~13 essential operational scripts"
echo "  - Remaining in root: 4 essential documentation files"
echo ""
echo "Next steps:"
echo "  1. Review archived files in scripts/archive/"
echo "  2. Check docs/ directory structure"
echo "  3. Commit organized files to git"
echo "  4. Review PROJECT_CLEANUP_PLAN.md for details"
