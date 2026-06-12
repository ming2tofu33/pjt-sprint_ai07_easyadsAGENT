# Orchestrator Test Consolidation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the number of orchestrator test files from over 240 highly fragmented files to a smaller, more maintainable set by merging domain-specific tests and removing redundant ones.

**Architecture:** Group tests by domain (`compliance`, `copy`, `ocr/quality_gate`, `typography/layout`, `generation_jobs`, `usage`, `t2i/vision`). For each domain, we will create a single unified test file, copy the logic over, ensure tests pass, and delete the fragmented ones.

**Tech Stack:** Python, pytest

---

### Task 1: Consolidate Compliance Tests

**Files:**
- Create: `orchestrator/tests/test_compliance_unified.py`
- Delete: `orchestrator/tests/test_compliance_*.py` (8 files)

- [ ] **Step 1: Consolidate into unified file**
Run a command to concatenate all compliance tests, then manually resolve duplicate imports.
```bash
cat orchestrator/tests/test_compliance_*.py > orchestrator/tests/test_compliance_unified.py
```
*Note: An engineer or subagent needs to open `test_compliance_unified.py` to clean up duplicate imports and ensure all fixtures are properly placed at the top.*

- [ ] **Step 2: Run test to verify it passes**
Run: `PYTHONPATH=/home/spai0722/codeit ./.venv/bin/pytest orchestrator/tests/test_compliance_unified.py -v`
Expected: All tests PASS

- [ ] **Step 3: Delete fragmented files and rename**
```bash
rm orchestrator/tests/test_compliance_*.py
mv orchestrator/tests/test_compliance_unified.py orchestrator/tests/test_compliance.py
```

- [ ] **Step 4: Commit**
```bash
git add orchestrator/tests/test_compliance*.py
git commit -m "test(orchestrator): consolidate compliance tests"
```

### Task 2: Consolidate Copy & Tone Tests

**Files:**
- Create: `orchestrator/tests/test_copywriting_unified.py`
- Delete: `orchestrator/tests/test_copy_*.py` (17 files)

- [ ] **Step 1: Consolidate into unified file**
```bash
cat orchestrator/tests/test_copy_*.py > orchestrator/tests/test_copywriting_unified.py
```
*Clean up duplicate imports and group related fixtures.*

- [ ] **Step 2: Run test to verify it passes**
Run: `PYTHONPATH=/home/spai0722/codeit ./.venv/bin/pytest orchestrator/tests/test_copywriting_unified.py -v`
Expected: All tests PASS

- [ ] **Step 3: Delete fragmented files and rename**
```bash
rm orchestrator/tests/test_copy_*.py
mv orchestrator/tests/test_copywriting_unified.py orchestrator/tests/test_copywriting.py
```

- [ ] **Step 4: Commit**
```bash
git add orchestrator/tests/test_copy*.py orchestrator/tests/test_copywriting.py
git commit -m "test(orchestrator): consolidate copy and tone tests"
```

### Task 3: Consolidate OCR & Quality Gate Tests

**Files:**
- Create: `orchestrator/tests/test_gates_unified.py`
- Delete: `orchestrator/tests/test_ocr_gate_*.py` and `orchestrator/tests/test_quality_gate_*.py` (18 files)

- [ ] **Step 1: Consolidate into unified file**
```bash
cat orchestrator/tests/test_ocr_gate_*.py orchestrator/tests/test_quality_gate_*.py > orchestrator/tests/test_gates_unified.py
```
*Clean up duplicate imports and group related fixtures.*

- [ ] **Step 2: Run test to verify it passes**
Run: `PYTHONPATH=/home/spai0722/codeit ./.venv/bin/pytest orchestrator/tests/test_gates_unified.py -v`
Expected: All tests PASS

- [ ] **Step 3: Delete fragmented files and rename**
```bash
rm orchestrator/tests/test_ocr_gate_*.py orchestrator/tests/test_quality_gate_*.py
mv orchestrator/tests/test_gates_unified.py orchestrator/tests/test_gates.py
```

- [ ] **Step 4: Commit**
```bash
git add orchestrator/tests/test_ocr_gate_*.py orchestrator/tests/test_quality_gate_*.py orchestrator/tests/test_gates.py
git commit -m "test(orchestrator): consolidate ocr and quality gate tests"
```

### Task 4: Consolidate Typography & Layout Tests

**Files:**
- Create: `orchestrator/tests/test_typography_unified.py`
- Delete: `orchestrator/tests/test_typography_*.py` and `orchestrator/tests/test_text_*.py`

- [ ] **Step 1: Consolidate into unified file**
```bash
cat orchestrator/tests/test_typography_*.py orchestrator/tests/test_text_*.py > orchestrator/tests/test_typography_unified.py
```
*Clean up duplicate imports and group related fixtures.*

- [ ] **Step 2: Run test to verify it passes**
Run: `PYTHONPATH=/home/spai0722/codeit ./.venv/bin/pytest orchestrator/tests/test_typography_unified.py -v`
Expected: All tests PASS

- [ ] **Step 3: Delete fragmented files and rename**
```bash
rm orchestrator/tests/test_typography_*.py orchestrator/tests/test_text_*.py
mv orchestrator/tests/test_typography_unified.py orchestrator/tests/test_typography.py
```

- [ ] **Step 4: Commit**
```bash
git add orchestrator/tests/test_typography*.py orchestrator/tests/test_text_*.py
git commit -m "test(orchestrator): consolidate typography and text layout tests"
```

### Task 5: Consolidate Generation Job Tests

**Files:**
- Create: `orchestrator/tests/test_generation_jobs_unified.py`
- Delete: `orchestrator/tests/test_generation_job_*.py` (13 files)

- [ ] **Step 1: Consolidate into unified file**
```bash
cat orchestrator/tests/test_generation_job_*.py > orchestrator/tests/test_generation_jobs_unified.py
```
*Clean up duplicate imports.*

- [ ] **Step 2: Run test to verify it passes**
Run: `PYTHONPATH=/home/spai0722/codeit ./.venv/bin/pytest orchestrator/tests/test_generation_jobs_unified.py -v`
Expected: All tests PASS

- [ ] **Step 3: Delete fragmented files and rename**
```bash
rm orchestrator/tests/test_generation_job_*.py
mv orchestrator/tests/test_generation_jobs_unified.py orchestrator/tests/test_generation_jobs.py
```

- [ ] **Step 4: Commit**
```bash
git add orchestrator/tests/test_generation_job*.py
git commit -m "test(orchestrator): consolidate generation job tests"
```

### Task 6: Consolidate T2I & Vision Tests

**Files:**
- Create: `orchestrator/tests/test_vision_t2i_unified.py`
- Delete: `orchestrator/tests/test_t2i_*.py` and `orchestrator/tests/test_vision_*.py` (15 files)

- [ ] **Step 1: Consolidate into unified file**
```bash
cat orchestrator/tests/test_t2i_*.py orchestrator/tests/test_vision_*.py > orchestrator/tests/test_vision_t2i_unified.py
```
*Clean up duplicate imports.*

- [ ] **Step 2: Run test to verify it passes**
Run: `PYTHONPATH=/home/spai0722/codeit ./.venv/bin/pytest orchestrator/tests/test_vision_t2i_unified.py -v`
Expected: All tests PASS

- [ ] **Step 3: Delete fragmented files and rename**
```bash
rm orchestrator/tests/test_t2i_*.py orchestrator/tests/test_vision_*.py
mv orchestrator/tests/test_vision_t2i_unified.py orchestrator/tests/test_vision_t2i.py
```

- [ ] **Step 4: Commit**
```bash
git add orchestrator/tests/test_t2i_*.py orchestrator/tests/test_vision_*.py orchestrator/tests/test_vision_t2i.py
git commit -m "test(orchestrator): consolidate t2i and vision tests"
```
