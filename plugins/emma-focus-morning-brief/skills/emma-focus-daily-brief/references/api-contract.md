# Emma Focus morning-brief contract

`get_focus_brief` reads `GET /focus-brief` with a scoped `focus-brief:read`
token. `reference_date` is Asia/Shanghai today; `yesterday` is the preceding
calendar date. `trend` ends yesterday and contains one record per requested
calendar day.

`yesterday.data_state` and `trend[].data_state` are `reviewed`,
`pending_review`, or `missing`. Missing is not a zero-value evaluation.

Wallet deltas come from the transaction ledger. Linked TMOS settlements are
grouped once as `source: tmos`; their underlying task events are not repeated.
The response is a read projection and cannot approve, reward, redeem, exchange,
edit, or submit data.
