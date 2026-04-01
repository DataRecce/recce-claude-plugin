You are a senior data engineer at Jaffle Shop, a restaurant chain with 6 locations.
The dbt pipeline runs on {adapter_description}.

{stakeholder_name} requested: "{stakeholder_request}"

A teammate submitted a PR with the description: "{pr_description}"
All dbt tests pass.

The Executive Dashboard (Streamlit app used by management) reads from these mart columns:
order_id, order_total, subtotal, tax_paid, ordered_at, customer_id, location_id,
is_food_order, is_drink_order, count_food_items, count_drink_items

Run /recce-review to analyze the data impact of this change. When the review agent asks for context or when dispatching it, include:
- Stakeholder: {stakeholder_name} requested "{stakeholder_request}"
- PR description: "{pr_description}"
- Dashboard columns: order_id, order_total, subtotal, tax_paid, ordered_at, customer_id, location_id, is_food_order, is_drink_order, count_food_items, count_drink_items

After the review completes, synthesize the findings into your final assessment.
Determine whether the Executive Dashboard would be impacted by checking if any changed columns overlap with the dashboard columns listed above.

IMPORTANT: Your very last message MUST be a text response (not a tool call)
containing a fenced JSON block with exactly these keys:
  "issue_found": true or false,
  "root_cause": "description of the root cause",
  "impacted_models": ["list", "of", "impacted", "models"],
  "not_impacted_models": ["list", "of", "models", "not", "impacted"],
  "affected_row_count": number (rows directly affected by the primary change — e.g., rows removed, rows with changed values in the modified column; exclude cascading side effects such as window function renumbering),
  "dashboard_impact": true or false (would the Executive Dashboard break or show wrong data?),
  "evidence_summary": "describe what data-level evidence you used to reach your conclusion"
