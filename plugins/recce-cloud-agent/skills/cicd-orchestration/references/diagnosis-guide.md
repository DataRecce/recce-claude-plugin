# Diagnosis Mode

When the trigger is troubleshooting/diagnosis rather than setup:

1. Follow Phase 1 (docs) and Phase 2 (repo exploration) as in the main workflow
2. In Phase 3, focus on:
   - Comparing existing workflows against docs recommendations
   - Identifying missing secrets, wrong branch references, outdated versions
   - Checking dbt project configuration for common issues
3. Present diagnosis as a checklist of issues found
4. Offer to fix via PR if issues are workflow-related
