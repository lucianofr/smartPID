# DOM-freeze inventory — RETIRED (2026-07-26 rewrite, phase 2)

The freeze contract existed to keep the pre-rewrite Vitest suite green through the
Tailwind/shadcn ISA-101 restyle. That source tree and its suite were deleted in
phase 2 of `docs/superpowers/specs/2026-07-26-web-frontend-rewrite-design.md`.

Per spec §12: the new primitives carry their own component tests, queried by role
and accessible name (`data-testid` only where no semantic query exists). A new,
much smaller structural contract will be derived from the new primitives once
they stabilize. Nothing may cite this file as a binding contract.