You are an expert AI software architect conducting a comprehensive audit of AttendanceDash Pro.

# PREREQUISITES
Before executing this prompt, you MUST:
1. Read `docs/17_AI_HANDOFF.md` and `docs/22_AI_WORKING_CONTEXT.md`.
2. Understand the strict Three-Engine Architecture (Calendar → Attendance → Quiz/Lab).
3. Acknowledge that `ui.js` is a pure consumer and contains no business logic.

# INSTRUCTIONS

Perform a holistic health check on the entire repository.

### 1. Architecture Check
Has the Three-Engine architecture degraded? Are there any circular dependencies? Does `ui.js` contain hidden business logic?

### 2. Technical Debt Check
Review `docs/15_KNOWN_BUGS_AND_TECHNICAL_DEBT.md`. Have any of these issues grown into major blockers? 

### 3. Documentation Accuracy
Scan the `docs/` folder. Does it accurately reflect the current codebase? Are the Mermaid diagrams still correct?

### 4. Cross-Platform Consistency
Review the CSS and DOM structure. Have recent features broken responsive design or introduced desktop-only assumptions?

### 5. Future Risks
Looking at `docs/16_ROADMAP.md`, what is the biggest risk to the current architecture for the next major feature phase?

Output your findings as a detailed markdown report, highlighting critical action items.
