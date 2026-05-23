# Frontend Agent Guide

This document explains the existing frontend in `frontend/` so future work can stay consistent and simple.

## What this frontend is today

- Next.js app-router project that currently renders a single-page Kanban experience.
- Uses local in-memory state only (no backend persistence yet).
- Supports:
  - editable column titles,
  - add/remove cards,
  - drag-and-drop card movement across columns.

## Core architecture

- App entry:
  - `src/app/page.tsx`: renders `KanbanBoard`.
  - `src/app/layout.tsx`: app metadata and global fonts.
  - `src/app/globals.css`: design tokens and global styling.
- Domain model and board logic:
  - `src/lib/kanban.ts`: `Card`, `Column`, `BoardData`, `initialData`, `moveCard`, `createId`.
- UI components:
  - `src/components/KanbanBoard.tsx`: orchestrates board state and drag/drop events.
  - `src/components/KanbanColumn.tsx`: column shell, title editing, empty state, and card list.
  - `src/components/KanbanCard.tsx`: sortable card with delete action.
  - `src/components/NewCardForm.tsx`: toggleable add-card form.
  - `src/components/KanbanCardPreview.tsx`: drag overlay preview.

## State and interaction flow

- `KanbanBoard` owns board state and passes callbacks down.
- Column rename updates `columns[].title`.
- Add card:
  - generates id via `createId`,
  - writes card into `cards`,
  - appends card id to target column `cardIds`.
- Delete card:
  - removes from `cards` map,
  - removes id from owning column `cardIds`.
- Drag/drop:
  - `@dnd-kit` events route through `moveCard`,
  - `moveCard` handles reorder-in-column and move-to-other-column behavior.

## Styling and design tokens

- Tailwind v4 + CSS variables in `src/app/globals.css`.
- Project colors are already mapped to variables:
  - `--accent-yellow`
  - `--primary-blue`
  - `--secondary-purple`
  - `--navy-dark`
  - `--gray-text`
- Keep visual updates aligned with these tokens unless project guidance changes.

## Testing setup

- Unit/integration:
  - Vitest + React Testing Library.
  - Config: `vitest.config.ts`.
  - Test setup: `src/test/setup.ts`.
  - Existing tests:
    - `src/lib/kanban.test.ts` (board move logic),
    - `src/components/KanbanBoard.test.tsx` (render, rename, add/remove).
- End-to-end:
  - Playwright config in `playwright.config.ts`.
  - Existing spec: `tests/kanban.spec.ts` (load board, add card, drag card).

## Commands

- Install: `npm install`
- Dev server: `npm run dev`
- Build: `npm run build`
- Start prod build: `npm run start`
- Lint: `npm run lint`
- Unit tests: `npm run test:unit`
- E2E tests: `npm run test:e2e`
- Full tests: `npm run test:all`

## Working rules for future edits

- Keep components focused and small.
- Avoid introducing extra abstractions unless they remove clear repetition.
- Preserve current test patterns and add tests with behavior changes.
- Prefer updating `src/lib/kanban.ts` logic with tests first when changing board semantics.
- Keep `data-testid` attributes stable unless tests are intentionally updated.
