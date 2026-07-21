# Agent Instructions

This document outlines the workflow and testing requirements for autonomous agents and contributors working on this project.

1. **Testing & Environment Safety**
   * Create complete test coverage for every feature.
   * Simulate databases and external environments; never run tests in the production environment.
   * Always clean up temporary testing environments and databases after tests run.

2. **Definition of Done**
   * A task is officially concluded only when all tests pass successfully.
   * **Do NOT automatically launch development environments (e.g. `Run-Dev.ps1`) when finishing tasks.** Keep the environment clean and let the user launch it manually.

3. **Local Commit Strategy**
   * Create a Git commit locally after the successful completion of each task.
   * Do not push commits to the remote repository.

4. **Baserow Configuration**
   * The Baserow database token is `C2nLVGVxMf8Fb53S8fUi72XQIbCSII7L`.

