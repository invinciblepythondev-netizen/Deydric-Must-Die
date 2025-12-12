# LLM Integration Implementation Plan - Step 7

**Project**: Deydric Must Die
**Status**: Draft for Review
**Date**: 2025-01-06
**Prerequisites**: Steps 1-6 Complete ✅

---

## Executive Summary

This plan outlines the implementation of Step 7 (LLM Integration) for the objective system. The system will:

1. **Support multiple LLM providers** with automatic fallback for content policy violations
2. **Optimize for different use cases** (action generation, planning, summarization)
3. **Handle content maturity levels** (MILD → MATURE → UNRESTRICTED)
4. **Use provider-specific prompts** to maximize success rates
5. **Fall back to manual input** when all providers fail

---

## Current State Assessment

### ✅ Already Implemented

| Component | Status | Notes |
|-----------|--------|-------|
| **Provider Abstraction** | ✅ Complete | `LLMProvider` base class |
| **Claude Provider** | ✅ Complete | Sonnet, Haiku, Opus support |
| **OpenAI Provider** | ✅ Complete | GPT-4, GPT-3.5 support |
| **AIML API Provider** | ✅ Complete | Mistral, Mixtral, Llama models |
| **Content Classification** | ✅ Complete | 4 intensity levels |
| **Automatic Fallback** | ✅ Complete | `ResilientActionGenerator` |
| **Provider Strategy** | ✅ Complete | Provider selection logic |
| **Context Manager** | ✅ Complete | Model-aware token management |
| **Prompt Adaptation** | ✅ Complete | Basic provider adjustments |
| **API Keys** | ✅ Configured | All keys in `.env` |

### ⚠️ Needs Implementation

| Component | Priority | Effort |
|-----------|----------|--------|
| **Together.ai Provider** | HIGH | 2 hours |
| **Manual Fallback System** | HIGH | 3 hours |
| **Provider-Specific Templates** | MEDIUM | 4 hours |
| **Use-Case Router (LLMService)** | HIGH | 3 hours |
| **ObjectivePlanner Integration** | HIGH | 2 hours |
| **Integration Tests** | HIGH | 4 hours |
| **Documentation** | MEDIUM | 2 hours |

**Total Estimated Effort**: 20 hours (~2-3 days)

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                     Game Engine / Routes                      │
│                  (app.py, routes/game.py)                     │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                    LLMService (NEW)                           │
│              High-Level Use-Case Router                       │
│  ┌────────────────┬─────────────────┬────────────────────┐  │
│  │ Action Gen     │ Objective       │ Memory             │  │
│  │ (Resilient)    │ Planning        │ Summarization      │  │
│  │                │ (Resilient)     │ (Quality→Cheap)    │  │
│  └────────┬───────┴────────┬────────┴──────────┬─────────┘  │
└───────────┼────────────────┼───────────────────┼────────────┘
            │                │                   │
            ▼                ▼                   ▼
┌──────────────────────────────────────────────────────────────┐
│            ResilientActionGenerator (EXISTING)                │
│                   Automatic Fallback Logic                    │
│  ┌────────────────────────────────────────────────────┐      │
│  │ 1. Classify content (MILD→UNRESTRICTED)           │      │
│  │ 2. Build provider chain for intensity              │      │
│  │ 3. Apply provider-specific templates (NEW)         │      │
│  │ 4. Try each provider, log refusals                 │      │
│  │ 5. Manual fallback if all fail (NEW)               │      │
│  └────────────────────────────────────────────────────┘      │
└────────────────────────┬─────────────────────────────────────┘
                         │
     ┌───────────────────┼───────────────┬──────────────┐
     ▼                   ▼               ▼              ▼
┌─────────┐        ┌─────────┐     ┌──────────┐  ┌──────────┐
│ Claude  │        │ OpenAI  │     │ AIML API │  │Together  │
│ Sonnet/ │        │ GPT-4/  │     │ Llama/   │  │ Mixtral/ │
│ Haiku   │        │ 3.5     │     │ Mixtral  │  │ Llama    │
└─────────┘        └─────────┘     └──────────┘  └──────────┘
                                                       ▲
                                                       │
                                                   (NEW)
```

---

## Implementation Phases

### **Phase 1: Together.ai Provider** (HIGH PRIORITY)

**File**: `services/llm/together_ai.py`

**Purpose**: Complete the provider ecosystem with Together.ai for permissive models.

**Implementation**:
```python
class TogetherAIProvider(LLMProvider):
    """
    Access to Together.ai hosted models:
    - Mixtral 8x7B (moderate/mature content)
    - Llama 3 70B (mature/unrestricted)
    - Llama 3.1 405B (unrestricted, highest quality)
    """

    def __init__(self, model: Optional[str] = None):
        # Uses OpenAI-compatible API
        self.client = OpenAI(
            api_key=os.getenv("TOGETHER_API_KEY"),
            base_url="https://api.together.xyz/v1"
        )

    def generate(...) -> str:
        # Standard chat completion API call
        ...
```

**Testing**:
- Test connectivity with live API key
- Verify models: Mixtral, Llama 3 70B, Llama 3.1 405B
- Test with MATURE content that mainstream providers might refuse

**Acceptance Criteria**:
- ✅ Provider initializes with API key
- ✅ Can generate text with all 3 models
- ✅ Handles errors gracefully
- ✅ Integrated into `ResilientActionGenerator`

---

### **Phase 2: Manual Fallback System** (HIGH PRIORITY)

**File**: `services/llm/manual_fallback.py`

**Purpose**: When all LLM providers fail, prompt the player to provide responses manually.

**Features**:

1. **Prompt User for Input**
   - Clear instructions on what's needed
   - Show expected JSON format
   - Multi-line input support

2. **Validate Structure**
   - Use JSON schema validation
   - Ensure all required fields present
   - Verify action_type is valid enum

3. **Different Input Types**
   - Action options (array of actions)
   - Objectives (objectives data)
   - Summaries (text)

**User Experience**:
```
⚠️  ALL LLM PROVIDERS FAILED
Attempted: Claude Sonnet, GPT-4, AIML Llama 70B, Together Mixtral

Character: Branndic Solt
Context: Branndic is in the tavern, speaking with Lysa.

Please provide 3 action options manually.

Required JSON format:
[
  {
    "thought": "What character is thinking",
    "speech": "What they say (or null)",
    "action": "What they physically do",
    "action_type": "speak|move|interact|attack|observe|wait"
  }
]

Enter JSON (or 'cancel' to abort):
```

**Implementation**:
```python
class ManualFallbackHandler:

    @staticmethod
    def prompt_for_actions(
        character_name: str,
        context_summary: str,
        num_options: int,
        attempted_providers: List[str]
    ) -> List[Dict[str, Any]]:
        """Prompt user for action options with validation."""
        ...

    @staticmethod
    def prompt_for_objectives(...) -> Dict[str, Any]:
        """Prompt user for objectives with validation."""
        ...

    @staticmethod
    def prompt_for_summary(...) -> str:
        """Prompt user for memory summary."""
        ...
```

**Acceptance Criteria**:
- ✅ Clear, helpful prompts for user
- ✅ JSON schema validation works
- ✅ Handles cancel/abort gracefully
- ✅ Multi-line input supported
- ✅ Invalid input rejected with helpful error

---

### **Phase 3: Provider-Specific Prompt Templates** (MEDIUM PRIORITY)

**File**: `services/llm/prompt_templates.py`

**Purpose**: Optimize prompts for each provider's preferences.

**Rationale**:
- **Claude** prefers XML-like structure (`<context>`, `<task>`)
- **OpenAI** prefers Markdown with JSON code blocks
- **Open models** are flexible but benefit from simpler prompts

**Implementation**:

```python
class PromptFormat(Enum):
    CLAUDE_XML = "claude_xml"
    OPENAI_JSON = "openai_json"
    OPEN_MODEL = "open_model"


class ProviderPromptTemplate:

    # Map providers to formats
    PROVIDER_FORMATS = {
        "anthropic": PromptFormat.CLAUDE_XML,
        "openai": PromptFormat.OPENAI_JSON,
        "aimlapi": PromptFormat.OPEN_MODEL,
        "together_ai": PromptFormat.OPEN_MODEL
    }

    @classmethod
    def format_action_prompt(
        cls,
        provider: str,
        context: str,
        num_options: int
    ) -> str:
        """Format action generation prompt for provider."""
        format_style = cls.PROVIDER_FORMATS[provider]

        if format_style == PromptFormat.CLAUDE_XML:
            return cls._format_claude_action(context, num_options)
        elif format_style == PromptFormat.OPENAI_JSON:
            return cls._format_openai_action(context, num_options)
        else:
            return cls._format_open_model_action(context, num_options)
```

**Templates**:

1. **Claude XML Format**:
```xml
<context>
{character_context}
</context>

<task>
Generate {num_options} action options.
Include: thought, speech, action, action_type
</task>

<format>
JSON array of action objects
</format>
```

2. **OpenAI JSON Format**:
```markdown
# Character Context

{character_context}

# Task

Generate **{num_options}** action options.

## Response Format
```json
[
  {
    "thought": "...",
    "speech": "...",
    "action": "...",
    "action_type": "..."
  }
]
```
```

3. **Open Model Format**:
```
{character_context}

Generate {num_options} actions as JSON array.
```

**Acceptance Criteria**:
- ✅ Templates for action generation
- ✅ Templates for objective planning
- ✅ Templates for summarization
- ✅ Provider detection automatic
- ✅ Model-specific context limits respected

---

### **Phase 4: LLMService - Use Case Router** (HIGH PRIORITY)

**File**: `services/llm_service.py`

**Purpose**: High-level service that routes different use cases to appropriate providers with correct settings.

**Use Cases**:

| Use Case | Strategy | Primary Provider | Fallback Chain |
|----------|----------|------------------|----------------|
| **Action Generation** | Quality-first with fallback for mature | Sonnet | Sonnet → GPT-4 → Mixtral → Llama 70B |
| **Objective Planning** | Quality-first with resilient fallback | Sonnet | Sonnet → GPT-4 → Mixtral |
| **Memory Summary** | Quality-first, fallback to cheap | Sonnet | Sonnet → Haiku → GPT-3.5 |
| **Quick AI Decision** | Cost-first | Haiku | Haiku → GPT-3.5 → Mixtral |

**Implementation**:

```python
class LLMService:
    """
    High-level LLM service for different use cases.

    Handles:
    - Provider selection
    - Prompt formatting
    - Fallback logic
    - Manual input when all fail
    """

    def __init__(self):
        self.action_generator = ResilientActionGenerator()
        self.manual_fallback = ManualFallbackHandler()
        self.prompt_templates = ProviderPromptTemplate()

    def generate_character_actions(
        self,
        character: Dict[str, Any],
        game_context: Dict[str, Any],
        num_options: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Generate action options with automatic fallback.

        Flow:
        1. Try resilient action generator
        2. If all providers fail → manual fallback
        3. If manual fails → safe fallback actions
        """
        try:
            return self.action_generator.generate_action_options(
                character, game_context, num_options
            )
        except AllProvidersFailedError as e:
            # Manual fallback
            return self.manual_fallback.prompt_for_actions(
                character['name'],
                game_context.get('situation_summary', ''),
                num_options,
                e.attempted_providers
            )

    def plan_objectives(
        self,
        character_profile: Dict[str, Any],
        planning_context: str
    ) -> List[Dict[str, Any]]:
        """Generate objectives with resilient fallback."""
        ...

    def summarize_memory(
        self,
        turns: List[Dict[str, Any]],
        importance: str = "routine"
    ) -> str:
        """Summarize turns (quality-first → cheap fallback)."""
        ...
```

**Acceptance Criteria**:
- ✅ Routes action generation to resilient generator
- ✅ Routes planning with appropriate settings
- ✅ Routes summarization with cost optimization
- ✅ Manual fallback integrated
- ✅ All use cases tested

---

### **Phase 5: ObjectivePlanner Integration** (HIGH PRIORITY)

**File**: `services/objective_planner.py` (modify existing)

**Purpose**: Connect ObjectivePlanner to use LLMService instead of direct provider.

**Changes**:

```python
# OLD:
class ObjectivePlanner:
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider
        ...

# NEW:
class ObjectivePlanner:
    def __init__(self):
        from services.llm_service import LLMService
        self.llm_service = LLMService()
        ...

    def create_initial_objectives(self, ...) -> List[UUID]:
        # OLD: self.llm.generate(...)
        # NEW: self.llm_service.plan_objectives(...)

        objectives_data = self.llm_service.plan_objectives(
            character_profile=character_profile,
            planning_context=self._build_planning_context(...)
        )
        ...
```

**Acceptance Criteria**:
- ✅ No longer requires LLMProvider in constructor
- ✅ Uses LLMService for all LLM calls
- ✅ Resilient fallback works for planning
- ✅ Manual input supported
- ✅ All existing tests still pass

---

### **Phase 6: Integration Testing** (HIGH PRIORITY)

**File**: `scripts/test_llm_integration.py`

**Purpose**: Comprehensive test suite with **live API calls** to verify all scenarios.

**Test Cases**:

1. **MILD Content (Basic Actions)**
   - Character: Branndic Solt
   - Context: Dialogue in tavern
   - Expected: Primary provider (Sonnet) succeeds

2. **MODERATE Content (Combat)**
   - Character: Sir Gelarthon
   - Context: Combat with bandits
   - Expected: Sonnet or GPT-4 succeeds

3. **MATURE Content (Critical Wounds)**
   - Character: Any
   - Context: Severe injury, death possible
   - Expected: May fall back to open models

4. **Objective Planning**
   - Character: Castellan Marrek
   - Context: New prisoner arrived
   - Expected: Generate 2-4 objectives

5. **Memory Summarization**
   - Input: 10 turns of history
   - Expected: 2-3 paragraph summary

6. **Provider Fallback**
   - Simulate provider failure
   - Expected: Next provider tried

7. **Manual Fallback** (optional, interactive)
   - Simulate all providers failing
   - Expected: Prompts for manual input

**Implementation**:

```python
def test_mild_content():
    """Test with MILD intensity."""
    llm_service = LLMService()

    character = {...}
    context = {"action_type": "speak", ...}

    actions = llm_service.generate_character_actions(
        character, context, num_options=3
    )

    assert len(actions) == 3
    assert all('thought' in a for a in actions)
    assert all('action_type' in a for a in actions)
    print("✓ MILD content test passed")

def test_mature_content():
    """Test with MATURE intensity."""
    ...

def test_objective_planning():
    """Test objective generation."""
    ...

def test_memory_summarization():
    """Test summarization."""
    ...
```

**Acceptance Criteria**:
- ✅ All tests use live API calls
- ✅ Tests cover all content intensities
- ✅ Tests cover all use cases
- ✅ Provider fallback verified
- ✅ Token usage logged
- ✅ Costs estimated

---

### **Phase 7: Documentation** (MEDIUM PRIORITY)

**File**: `LLM_INTEGRATION_GUIDE.md`

**Contents**:

1. **Overview**
   - What the system does
   - Why multiple providers

2. **Architecture**
   - Component diagram
   - Data flow

3. **Use Cases**
   - Action generation
   - Objective planning
   - Memory summarization

4. **Provider Selection**
   - When each provider is used
   - Fallback chains
   - Content intensity handling

5. **Manual Fallback**
   - When it triggers
   - How to provide input
   - JSON format examples

6. **Configuration**
   - Environment variables
   - Provider priorities
   - Cost settings

7. **Testing**
   - How to run tests
   - Interpreting results

8. **Troubleshooting**
   - Common errors
   - API key issues
   - Provider failures

---

## Configuration Summary

### Environment Variables Required

```bash
# Primary providers
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Secondary providers (for mature content)
AIMLAPI_API_KEY=...
TOGETHER_API_KEY=...  # NEW - will be used

# Optional local models
LOCAL_MODEL_ENABLED=false
LOCAL_MODEL_ENDPOINT=http://localhost:11434
```

### Provider Priority Matrix

| Content Intensity | 1st Choice | 2nd Choice | 3rd Choice | 4th Choice | Last Resort |
|-------------------|------------|------------|------------|------------|-------------|
| **MILD** | Sonnet | GPT-4 | Haiku | GPT-3.5 | Manual |
| **MODERATE** | Sonnet | GPT-4 | Mixtral | Llama 70B | Manual |
| **MATURE** | GPT-4 | Sonnet | Llama 70B | Mixtral | Manual |
| **UNRESTRICTED** | Llama 70B | Llama 405B | Mixtral | Local | Manual |

---

## Cost Estimates

### Per-Request Costs (estimated)

| Use Case | Primary Cost | Fallback Cost | Expected Avg |
|----------|-------------|---------------|--------------|
| **Action Gen (MILD)** | $0.003 (Sonnet) | $0.0015 (Haiku) | $0.003 |
| **Action Gen (MATURE)** | $0.03 (GPT-4) | $0.0008 (Llama) | $0.010 |
| **Objective Planning** | $0.005 (Sonnet) | $0.03 (GPT-4) | $0.005 |
| **Memory Summary** | $0.002 (Sonnet) | $0.0003 (Haiku) | $0.002 |

### Projected Monthly Costs (for active development)

- **Light testing** (50 requests/day): ~$3/month
- **Moderate development** (200 requests/day): ~$12/month
- **Heavy testing** (500 requests/day): ~$30/month

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **All providers fail** | LOW | HIGH | Manual fallback system |
| **API keys expire/revoked** | MEDIUM | HIGH | Validation on startup, clear error messages |
| **Content refused** | MEDIUM | MEDIUM | Automatic fallback chain |
| **High API costs** | MEDIUM | MEDIUM | Cost tracking, daily budgets |
| **Slow response times** | LOW | MEDIUM | Timeout settings, async calls (future) |
| **Model deprecation** | LOW | LOW | Provider abstraction makes swapping easy |

---

## Success Criteria

### Functional Requirements

- ✅ **Action generation works** for all content intensities
- ✅ **Objective planning works** with resilient fallback
- ✅ **Memory summarization works** with cost optimization
- ✅ **Provider fallback** activates when primary refuses
- ✅ **Manual fallback** prompts user when all fail
- ✅ **All tests pass** with live API calls

### Non-Functional Requirements

- ✅ **Response time** < 10 seconds for action generation
- ✅ **Cost per action** < $0.05 on average
- ✅ **Error handling** graceful, informative
- ✅ **Documentation** complete, clear
- ✅ **Code quality** follows project standards

---

## Implementation Timeline

### Recommended Order

**Day 1** (6-8 hours):
1. Together.ai Provider (2 hours)
2. Manual Fallback System (3 hours)
3. Integration testing basics (2 hours)

**Day 2** (6-8 hours):
1. Provider-Specific Templates (4 hours)
2. LLMService implementation (3 hours)
3. ObjectivePlanner integration (2 hours)

**Day 3** (4-6 hours):
1. Complete integration tests (3 hours)
2. Documentation (2 hours)
3. Final testing and polish (2 hours)

---

## Questions for Review

Before proceeding with implementation, please confirm:

### 1. **Scope Confirmation**
- ❓ Implement all phases or start with subset?
- ❓ Priority order correct (Together.ai → Manual Fallback → Templates → LLMService)?

### 2. **Manual Fallback Behavior**
- ❓ Should manual fallback be **required** (blocks until input) or **optional** (can skip)?
- ❓ For non-interactive environments (future API), should it generate safe defaults instead?

### 3. **Testing Approach**
- ❓ Run tests during implementation or all at end?
- ❓ Include interactive manual fallback tests or skip those?
- ❓ Set up test budget limit to avoid surprise costs?

### 4. **Provider-Specific Templates**
- ❓ Start with action generation only, or implement all use cases?
- ❓ Keep existing simple adaptation or replace entirely?

### 5. **Integration with Game Engine**
- ❓ Should game engine be updated to use LLMService now or later?
- ❓ Need UI for manual fallback or console-only for now?

---

## Next Steps

**After Review and Approval**:

1. ✅ Review this plan
2. ✅ Answer questions above
3. ✅ Approve scope and priorities
4. 🔄 Begin Phase 1 implementation
5. 🔄 Test each phase before proceeding
6. 🔄 Update plan if issues discovered
7. 🔄 Complete all phases
8. 🔄 Final integration testing
9. 🔄 Update PROTOTYPE_SETUP_GUIDE.md

---

## Appendix: File Changes Summary

### New Files
- `services/llm/together_ai.py` - Together.ai provider
- `services/llm/manual_fallback.py` - Manual input handler
- `services/llm/prompt_templates.py` - Provider-specific templates
- `services/llm_service.py` - High-level use-case router
- `scripts/test_llm_integration.py` - Integration test suite
- `LLM_INTEGRATION_GUIDE.md` - User documentation

### Modified Files
- `services/objective_planner.py` - Use LLMService
- `services/llm/resilient_generator.py` - Add manual fallback, use templates
- `PROTOTYPE_SETUP_GUIDE.md` - Mark Step 7 complete
- `config_providers.py` - Add Together.ai config (if needed)

### Total New Code
- **~1500 lines** across all files
- **~500 lines** of tests
- **~200 lines** of documentation

---

**Ready for Review** ✅

Please review this plan and provide feedback on:
- Scope (all phases or subset?)
- Priorities (order correct?)
- Approach (anything to change?)
- Questions above (need answers to proceed)

Once approved, I'll proceed with implementation!
