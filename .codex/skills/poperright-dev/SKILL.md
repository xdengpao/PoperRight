---
name: poperright-dev
description: Use for PoperRight/A-share quantitative trading system development, especially new features, complex changes, quick fixes, data consistency work, backend/frontend/database changes, or any request that asks Codex to act as the project's quant development engineer. Loads project steering docs, chooses Spec or Vibe workflow, and enforces code quality review.
metadata:
  short-description: PoperRight quant development workflow
---

# PoperRight Quant Development

Use this skill when developing, fixing, or reviewing functionality in the PoperRight A-share quantitative trading system.

## Startup Context

Before starting feature work or non-trivial code changes, read these project steering files:

1. `.kiro/steering/product.md` - product definition and core capabilities
2. `.kiro/steering/tech.md` - architecture and tech stack
3. `.kiro/steering/structure.md` - directory structure and module ownership
4. `.kiro/steering/data-consistency.md` - data consistency rules

After reading, briefly confirm the relevant architecture understanding to the user.

## Choose Workflow

For new features or complex changes, ask the user to choose:

- **Spec mode**: Requirements -> Design -> Tasks. Use for new features, large behavior changes, or work where traceability matters.
- **Vibe mode**: Direct implementation. Use for small fixes, focused refactors, and quick improvements.

If the user explicitly asks for direct implementation or the change is clearly small, proceed in Vibe mode without blocking on a workflow question.

## Spec Mode

Create a folder under `.kiro/specs/` named with English kebab-case, such as `screener-data-alignment-fix`.

Generate these files in order, asking for confirmation after each major document:

1. `requirements.md`
   - Background and feature summary
   - Glossary if needed
   - Numbered requirements with user stories and SHALL/WHEN/IF-THEN acceptance criteria

2. `design.md`
   - Overview and design principles
   - Mermaid architecture diagram when useful
   - Technical implementation plan with files, classes, functions, and data structures
   - Backward compatibility notes

3. `tasks.md`
   - Phased task list
   - Use `- [ ]` checkboxes
   - Keep tasks independently verifiable

After all three documents are complete, ask the user whether to:

1. Execute tasks
2. Cross-check requirements, design, tasks, and existing code for consistency
3. Stop after documentation

When executing tasks, update `tasks.md` from `- [ ]` to `- [x]` as each task completes. If a task cannot pass review after retries, mark it `- [!]` with the failure reason.

## Vibe Mode

Implement directly without creating spec documents. Keep changes focused, follow existing architecture, and validate with the narrowest meaningful tests or checks.

## Code Quality Review

After generating or modifying code, perform a self-review using `.kiro/hooks/code-quality-review.kiro.hook` when present. Review for:

- Code smells, dead code, duplicated logic, excessive complexity
- Design pattern fit or misuse
- Language and framework best practices
- Naming, comments, nesting, and readability
- Maintainability and coupling
- Performance risks or avoidable work

If review fails:

1. Fix issues and review again.
2. If it still fails, fix and review one more time.
3. On a third failure, report the unresolved issues. In Spec mode, mark the task `- [!]`; in Vibe mode, report the failed review clearly.

## Project Conventions

- Documentation and code comments should be Chinese unless existing local style says otherwise.
- Variables, functions, classes, and modules use English names.
- Follow existing project style and architecture.
- Database work uses SQLAlchemy.
- Async code uses `asyncio`.
- Monetary values use `Decimal`.
- Percentage values use `float`.
- Stock codes are six-digit numeric strings.
