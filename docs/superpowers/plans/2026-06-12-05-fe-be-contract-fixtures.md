# FE BE Contract Fixtures Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent FE and orchestrator from silently drifting on generation stage names and interrupt payload shapes.

**Architecture:** Put small JSON fixtures in `apps/web/types/contracts`. FE tests assert parsers understand the fixtures, and BE tests assert backend constants/builders still match them. This is a contract-test layer, not a shared runtime package.

**Tech Stack:** JSON fixtures, Vitest, Pytest, TypeScript, Pydantic/FastAPI models.

---

## File Structure

- Create `apps/web/types/contracts/generation-stages.json`
- Create `apps/web/types/contracts/generation-job-interrupt.fixtures.json`
- Create `apps/web/lib/generation-job-stage.contract.test.ts`
- Create `apps/web/lib/generation-job-interrupt.contract.test.ts`
- Create `orchestrator/tests/test_generation_stage_contract.py`
- Create `orchestrator/tests/test_generation_interrupt_contract.py`

### Task 1: Stage Name Contract

**Files:**
- Create: `apps/web/types/contracts/generation-stages.json`
- Create: `apps/web/lib/generation-job-stage.contract.test.ts`
- Create: `orchestrator/tests/test_generation_stage_contract.py`

- [x] **Step 1: Create the fixture**

Create `apps/web/types/contracts/generation-stages.json`:

```json
{
  "version": 1,
  "stages": [
    "queued",
    "planning",
    "modal_submitted",
    "modal_running",
    "t2i_running",
    "storage",
    "waiting_user_input",
    "completed",
    "failed"
  ]
}
```

- [x] **Step 2: Add FE contract test**

Create `apps/web/lib/generation-job-stage.contract.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import contract from "@/types/contracts/generation-stages.json";
import { generationStageViewFromJob } from "./generation-job-stage";
import type { GenerationJob } from "./api-client";

function job(currentStage: string): GenerationJob {
  return {
    job_id: `job_${currentStage}`,
    status: currentStage === "failed" ? "failed" : currentStage === "completed" ? "done" : "running",
    progress: { progress_percent: 50, current_stage: currentStage, stage_order: [] },
    metadata: {}
  } as GenerationJob;
}

describe("generation stage FE/BE contract", () => {
  it.each(contract.stages)("renders a view for backend stage %s", (stage) => {
    const view = generationStageViewFromJob(job(stage));
    expect(view.label).toBeTruthy();
    expect(view.activeStepIndex).toBeGreaterThanOrEqual(0);
  });
});
```

- [x] **Step 3: Add BE contract test**

Create `orchestrator/tests/test_generation_stage_contract.py`:

```python
import json
from pathlib import Path


def test_backend_progress_stages_are_listed_in_frontend_contract():
    contract_path = Path(__file__).resolve().parents[2] / "apps/web/types/contracts/generation-stages.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    expected = set(contract["stages"])
    backend_known = {
        "queued",
        "planning",
        "modal_submitted",
        "modal_running",
        "t2i_running",
        "storage",
        "waiting_user_input",
        "completed",
        "failed",
    }

    assert backend_known <= expected
```

- [x] **Step 4: Run tests**

Run:

```bash
cd apps/web && npx vitest run lib/generation-job-stage.contract.test.ts
cd ../..
EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests/test_generation_stage_contract.py -q
```

Expected: PASS. If the FE mapper does not support a listed stage, update `apps/web/lib/generation-job-stage.ts` in this task.

- [x] **Step 5: Commit**

```bash
git add apps/web/types/contracts/generation-stages.json apps/web/lib/generation-job-stage.contract.test.ts orchestrator/tests/test_generation_stage_contract.py
git commit -m "test(contract): pin generation stage names"
```

### Task 2: Interrupt Payload Contract

**Files:**
- Create: `apps/web/types/contracts/generation-job-interrupt.fixtures.json`
- Create: `apps/web/lib/generation-job-interrupt.contract.test.ts`
- Create: `orchestrator/tests/test_generation_interrupt_contract.py`

- [x] **Step 1: Create interrupt fixture**

Create `apps/web/types/contracts/generation-job-interrupt.fixtures.json`:

```json
{
  "version": 1,
  "optionQuestion": {
    "type": "option_question",
    "field": "business_type",
    "question": "어떤 업종의 광고인가요?",
    "required": true,
    "options": [
      { "id": "cafe", "label": "카페/디저트", "value": "cafe" },
      { "id": "restaurant", "label": "음식점/식당", "value": "restaurant" }
    ],
    "context": {
      "business_type": null,
      "item_or_service": "아이스 아메리카노",
      "ad_purpose": "신메뉴 홍보"
    }
  },
  "copySelection": {
    "type": "copy_selection",
    "field": "selected_copy_id",
    "question": "사용할 문구를 골라주세요.",
    "required": true,
    "options": [
      { "id": "copy_1", "label": "오늘 한 잔, 시원하게", "value": "copy_1" },
      { "id": "copy_2", "label": "지금 필요한 커피 한 잔", "value": "copy_2" }
    ]
  }
}
```

- [x] **Step 2: Add FE parser test**

Create `apps/web/lib/generation-job-interrupt.contract.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import fixtures from "@/types/contracts/generation-job-interrupt.fixtures.json";
import { parseGenerationJobInterrupt } from "./generation-job-interrupt";

describe("generation job interrupt contract", () => {
  it("parses backend option-question fixture", () => {
    const parsed = parseGenerationJobInterrupt(fixtures.optionQuestion);

    expect(parsed).not.toBeNull();
    expect(parsed?.field).toBe("business_type");
    expect(parsed?.options.length).toBe(2);
  });

  it("parses backend copy-selection fixture", () => {
    const parsed = parseGenerationJobInterrupt(fixtures.copySelection);

    expect(parsed).not.toBeNull();
    expect(parsed?.field).toBe("selected_copy_id");
  });
});
```

- [x] **Step 3: Add BE fixture-shape test**

Create `orchestrator/tests/test_generation_interrupt_contract.py`:

```python
import json
from pathlib import Path


def test_interrupt_contract_fixture_has_required_fields():
    path = Path(__file__).resolve().parents[2] / "apps/web/types/contracts/generation-job-interrupt.fixtures.json"
    fixture = json.loads(path.read_text(encoding="utf-8"))

    option_question = fixture["optionQuestion"]
    assert option_question["type"] == "option_question"
    assert option_question["field"] == "business_type"
    assert option_question["required"] is True
    assert option_question["options"][0] == {"id": "cafe", "label": "카페/디저트", "value": "cafe"}

    copy_selection = fixture["copySelection"]
    assert copy_selection["type"] == "copy_selection"
    assert copy_selection["field"] == "selected_copy_id"
    assert copy_selection["options"][0]["id"] == "copy_1"
```

- [x] **Step 4: Run tests**

Run:

```bash
cd apps/web && npx vitest run lib/generation-job-interrupt.contract.test.ts
cd ../..
EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests/test_generation_interrupt_contract.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add apps/web/types/contracts/generation-job-interrupt.fixtures.json apps/web/lib/generation-job-interrupt.contract.test.ts orchestrator/tests/test_generation_interrupt_contract.py
git commit -m "test(contract): pin generation interrupt payloads"
```

## Final Verification

Run:

```bash
cd apps/web && npx vitest run lib/generation-job-stage.contract.test.ts lib/generation-job-interrupt.contract.test.ts && npx tsc --noEmit
cd ../..
EASYADS_DB_BACKEND=memory uv run python -m pytest orchestrator/tests/test_generation_stage_contract.py orchestrator/tests/test_generation_interrupt_contract.py -q
```

Expected: PASS.
