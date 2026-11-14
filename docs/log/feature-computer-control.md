# feature/computer-control log

## C1 (2026-11-14)
- SPIKE: read Hermes Agent computer-use code and cua-driver README/docs; both tried live on TextEdit.
- Finding: host already AX-trusted, so both paths listed TextEdit controls with no prompts.
- Decision: thin pyobjc layer (macOS-only, text-only, ~30-line AX walk works; cua-driver adds 50 MB binary + daemon + its own TCC identity).
- Gotchas recorded in notes: pid via CGWindowList (NSRunningApplication returns -1 on macOS 27); skip palette windows.
- Added pyobjc-framework-ApplicationServices as a dev dependency for the spike; C5 promotes it if needed.
