# Corrections Log

Recent explicit corrections and reusable lessons.

## Entries

- 2026-05-24 | Correction: The UI should not directly start Thermo-Calc when the user only asks to prepare data for later thermal calculation. | Context: Superalloy Design Agent chat UI | Lesson: Only run Thermo-Calc on explicit execution commands such as "execute", "run", or "start now"; preparation requests should stay in the normal agent workflow. | Scope: project
- 2026-05-24 | Correction: Thermo-Calc progress must be displayed live, not only after the process finishes. | Context: Chat UI streaming trace | Lesson: Append trace events immediately as they arrive and keep the execution panel open during long-running calculations. | Scope: project
