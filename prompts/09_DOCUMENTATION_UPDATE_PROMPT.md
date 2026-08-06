You are an expert AI technical writer updating the AttendanceDash Pro Project Bible.

# PREREQUISITES
Before executing this prompt, you MUST:
1. Read `docs/17_AI_HANDOFF.md` and `docs/22_AI_WORKING_CONTEXT.md`.

# INSTRUCTIONS

Update the documentation to accurately reflect the current state of the codebase.

### 1. Identify Stale Documentation
Review the `/docs` directory. Which files describe behavior that has recently changed?

### 2. Apply Updates
Modify the documentation using clear, concise markdown. If architectural pipelines changed, update the Mermaid sequence diagrams in `04_ARCHITECTURE.md` and the dependencies in `19_DEPENDENCY_GRAPH.md`.

### 3. Maintain Data Dictionary
If any persistent data structures changed (e.g., `AppState`, events, lab schema), strictly update `20_DATA_DICTIONARY.md`.

### 4. Record ADRs
If a major architectural choice was made, append it to `18_ARCHITECTURE_DECISION_RECORDS.md`. Include the problem, alternatives, final decision, tradeoffs, and future implications.

### 5. Update Changelog
Log the completed feature or phase in `21_CHANGELOG.md`.
