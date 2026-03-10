# TODO  
  
## Bugs  
  
### 1. Tables rendering with extra_verbose (IDs in brackets)  
**Problem:** When \"Show IDs in [brackets]\" option is enabled, tables display incorrectly - most columns are empty.  
  
**Cause:** Rendering functions use hardcoded column names, but with `extra_verbose=True` columns have different names (e.g., `Date [duedate]` instead of `Date`).  
  
**Solution:** Refactor rendering functions for dynamic column detection.  
  
---  
  
## Optimization  
  
### 2. Duplicate Jira API requests  
**Problem:** 2 requests per client during report generation.  
  
**Solution:** Make 2 requests for all clients with needed filters, then process per client. 
