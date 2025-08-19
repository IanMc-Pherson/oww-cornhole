# Cornhole Tournament MVP — Product & Tech Spec (v0)

## 0) Goals & Non-Goals

**Goals**

* Players scan QR → create or join a 2-person team (optional sub) for a single tournament.
* Admin can lock registration, seed, generate single-elim bracket, and auto-schedule matches to courts/time slots.
* Scorekeepers submit final scores; bracket updates live (polling).
* Public read-only views: rules, bracket, schedule, “now / next”.
* Reliable, low-friction, phone-friendly.

**Non-Goals (MVP)**

* No accounts/OAuth, no payments, no double-elim, no groups/pools, no push notifications.

---

## 1) System Overview

* **Frontend**: SPA (React or plain HTML+JS) hosted on **S3**, cached via **CloudFront**.
* **Backend**: **API Gateway (REST)** → **AWS Lambda (Python/FastAPI)**.
* **DB**: **DynamoDB** (single table).
* **Auth**:

  * **Public**: no login.
  * **Team edits**: team_code (short secret) + optional email/SMS OTP later.
  * **Admin/Scorekeeper**: shared **PIN** in `AWS SSM Parameter Store`, passed via header.
* **Realtime**: client polling every 10–15s for read endpoints.

---

## 2) Data Model (DynamoDB single-table)

**Table**: `tourney` (on-demand)

* **PK**: `pk`  | **SK**: `sk`

| pk            | sk                            | attributes (JSON)                                                                                                            |         |        |                                                                                       |           |
| ------------- | ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ------- | ------ | ------------------------------------------------------------------------------------- | --------- |
| `TOURN#<tid>` | `META`                        | name, location, tz, start_time_iso, format:"single_elim", rules_md_url, num_courts, match_duration_min, state:{draft | open    | locked | in_progress                                                                          | complete} |
| `TOURN#<tid>` | `TEAM#<teamId>`               | team_name, players:[{name, contact?}], captain_contact?, sub? , seed?, check_in:bool, team_code (secret)               |         |        |                                                                                       |           |
| `TOURN#<tid>` | `MATCH#<matchId>`             | round:int, index:int, teamA_id?, teamB_id?, court?:string, start_slot?:iso, status:{scheduled                         | playing | final  | forfeit}, score:{a:int,b:int}, winner_team_id?, next_match_id?, next_slot:{"A" | "B"}      |
| `TOURN#<tid>` | `COURT#<courtId>`             | name, active:bool                                                                                                           |         |        |                                                                                       |           |
| `TOURN#<tid>` | `SETTING#global`              | event_pin_hash (bcrypt), registration_close_iso                                                                          |         |        |                                                                                       |           |
| `TOURN#<tid>` | `SNAPSHOT#<yyyy-mm-ddThh:mm>` | computed bracket/schedule snapshot (for backup/export)                                                                       |         |        |                                                                                       |           |

**GSIs**

* `GSI1`: **by round**

  * `gsi1pk = TOURN#<tid>#ROUND#<round>`
  * `gsi1sk = index` (numeric as zero-padded string)
* `GSI2`: **by team**

  * `gsi2pk = TOURN#<tid>#TEAM#<teamId>`
  * `gsi2sk = status#<status>#match#<matchId>`

**Notes**

* `round=1` is first round; `index` is bracket slot within the round (0-based).
* `next_match_id` + `next_slot` tie progression.

---

## 3) Bracket & Scheduling (MVP rules)

**Seeding**

* Admin chooses “random” or “by check-in order”.
* Create seed list `S` (length = next power of two ≥ team_count). Add byes where needed.

**Bracket build**

* Standard single-elim pairing by seed (1 vs N, 2 vs N-1, …).
* Create `MATCH` items for round 1 using seeded team IDs (or byes).
* Pre-create all downstream matches with `next_match_id` references.

**Progression**

* On final score post:

  * Determine `winner_team_id`.
  * Write into `next_match_id` at slot `next_slot` if present.
  * If both slots of `next_match_id` filled and earlier than scheduled, leave schedule as-is (don’t auto-pull-forward in MVP).

**Scheduling**

* Inputs: `num_courts`, `match_duration_min`, `start_time_iso`.
* Greedy assign per round: iterate matches (by `index`), allocate to earliest available court/time. Store `court`, `start_slot`.
* Courts are independent lanes; no team consecutive-match guard in MVP.

**Forfeits**

* Admin can set a match to `forfeit` with a winner.

---

## 4) API (FastAPI over API Gateway)

### Headers

* `X-Event-PIN: <pin>` (Admin/Scorekeeper only)
* `X-Team-Code: <team_code>` (write ops for a team)

### Public (no auth)

* `GET /t/{tid}/public` → `{ name, location, tz, start_time, state, rules_url }`
* `GET /t/{tid}/rules` → raw markdown or pre-rendered HTML
* `GET /t/{tid}/bracket` → bracket tree + all matches (status, teams, scores, courts, times)
* `GET /t/{tid}/schedule` → flat list of matches `{round, index, court, start_slot, teamA, teamB, status}` (paginated)
* `GET /t/{tid}/team/{teamId}/next` → next scheduled/pending match for team

### Team (team_code required)

* `POST /t/{tid}/teams`
  **Body**: `{ team_name, players:[{name, contact?},{name, contact?}], sub?:{name, contact?}, captain_contact? }`
  **200**: `{ teamId, team_code }`
* `POST /t/{tid}/teams/{teamId}/join`
  **Body**: `{ name, contact? }` (adds/edits player 2 or sub)
  **200**: updated team
* `POST /t/{tid}/teams/{teamId}/checkin`
  **Body**: `{ check_in:true|false }`

### Scorekeeper (PIN)

* `GET /t/{tid}/matches?status=scheduled|playing` → assigned/open matches list
* `POST /t/{tid}/matches/{matchId}/score`
  **Body**: `{ score:{a:int,b:int} }`
  **Effects**: finalize, compute winner, progress to next match slot

### Admin (PIN)

* `POST /t/{tid}/lock_registrations`
* `POST /t/{tid}/seed` → `{ mode:"random"|"checkin" }` → returns seed list
* `POST /t/{tid}/build_bracket` → creates all MATCH items; returns round 1 summary
* `POST /t/{tid}/assign_courts` → `{ num_courts:int, match_duration_min:int, start_time_iso }` → updates matches with court/time
* `POST /t/{tid}/reschedule` → `{ matchId, court, start_slot }`
* `POST /t/{tid}/override_result` → `{ matchId, winner_team_id }` (re-wires downstream if needed)
* `GET /t/{tid}/export?format=csv|json|pdf` → S3 pre-signed URL

### Responses & Errors

* Use `{ ok:boolean, data?, error_code?, message? }`
* Common `error_code`: `BAD_REQUEST`, `UNAUTHORIZED`, `FORBIDDEN`, `CONFLICT`, `NOT_FOUND`, `STATE_INVALID`.

---

## 5) Validation Rules

* Team: name ≤ 40 chars; player names 1–60 chars; contacts optional; duplicate team names allowed (not unique), but **team_code** unique secret (6–8 chars base32).
* No team creates/edits after `state in {locked, in_progress, complete}`.
* Score submit: integers ≥0; match must be `scheduled|playing`; cannot finalize twice without admin override.
* Forfeit: requires one team present as winner.
* Seeding/build: available only when `state=open|locked` and before `in_progress`.
* State machine transitions:

  * `draft → open → locked → in_progress → complete`
  * Admin-only reverse: `in_progress → locked` (rare, for emergency) guarded by `override` flag.

---

## 6) Security

* PIN stored hashed (bcrypt) in SSM; Lambda fetches on cold start and caches.
* Rate-limit at API Gateway (e.g., 50 rps burst/25 steady per IP).
* Validate headers server-side; **never** trust client roles.
* Team writes require `X-Team-Code` matching stored code for `teamId`.
* CORS locked to your CloudFront domain.
* Audit log (CloudWatch): admin actions & score submissions (matchId, old→new).

---

## 7) Frontend Pages (minimal wireframes)

* **Home**: CTA: Create Team / Join Team / Rules / Live Bracket
* **Create Team**: form → show `team_code` + copy/share button
* **Join Team**: team selector or `teamId + team_code` field → add player/sub
* **My Team**: roster, check-in toggle, “next match”
* **Live Bracket**: bracket canvas + compact schedule table; poll 10–15s
* **Scorekeeper**: PIN gate → list of matches → score form
* **Admin**: counters (teams, checked-in), buttons (lock, seed, build, assign), manual reschedule table

---

## 8) Infrastructure (IaC sketched)

**Environment variables (Lambda)**

* `TABLE_NAME`, `TOURNAMENT_ID` (or multi-tournament aware), `PARAM_EVENT_PIN` (SSM path), `DEFAULT_TZ` (e.g., America/Toronto)
* `EXPORT_BUCKET`

**IAM (least privilege)**

* DynamoDB: `GetItem/PutItem/UpdateItem/Query/BatchWriteItem` on `TABLE_NAME`
* SSM: `GetParameter` (for PIN)
* S3: `PutObject/GetObject` on `EXPORT_BUCKET/*`
* CloudWatch Logs: create/write

**Deploy**

* Frontend build → S3 → CloudFront invalidation
* Backend → AWS SAM/Serverless Framework/Terraform

---

## 9) Algorithms (pseudocode)

**Team code**

```text
team_code = base32(random 40-bit) without padding; ensure no collision
```

**Bracket build (single-elim)**

```text
teams = list(checked_in OR all if none checked_in)
N = len(teams)
M = next_power_of_two(N)
seeds = seed(teams, mode)  # list length N
if N < M: add 'BYE' placeholders at the bottom to reach M

# Round 1 pairings by seed
pairs = [(1,M), (2,M-1), (3,M-2), ...]  # 1-based positions
create MATCH for each pair with teamA/ teamB (BYE allowed)

# Create downstream matches
for r in 2..log2(M):
  for i in 0..(M/(2^r)-1):
    create empty MATCH with next pointers set by tree topology

# Wire next pointers for round 1 matches to their parents
```

**Scheduling**

```text
courts = ["Court 1".."Court K"]
t = start_time
next_free = {court: t for court in courts}

for r in rounds ascending:
  for match in matches_in_round_sorted_by_index:
    court = argmin(next_free[court])
    start = next_free[court]
    assign(match.court=court, match.start_slot=start)
    next_free[court] = start + match_duration
```

**Score submit**

```text
require status in {"scheduled","playing"}
validate score a>=0,b>=0 and a!=b  # or allow win-by-1; adjust if house rules
winner = teamA if a>b else teamB
update match {status:"final", winner_team_id}
if next_match_id:
  update next_match slot (A or B) with winner_team_id
```

---

## 10) Rules Page (stub content contract)

* Markdown file in S3, linked via `rules_md_url`.
* Headings: Eligibility, Equipment, Scoring (e.g., 21 points, cancelation/scoring variant), Foot faults, Time limits, Forfeits, Conduct, Appeals.
* Allow a `GET /t/{tid}/rules` to return rendered HTML or raw markdown.

---

## 11) Testing Plan (MVP)

**Unit**

* Bracket build for N in {3,4,5,7,8,16}; verify byes; verify next pointers.
* Scheduling with K courts and duration; ensure no court overlap.
* Score submit progression into next match.
* State machine guardrails (can’t build when `in_progress` etc).

**Integration**

* Create → Join → Check-in → Lock → Seed → Build → Assign → Score flow.
* Forfeit path.
* Admin override result re-wires downstream.

**Smoke**

* Cold start PIN fetch, header checks, CORS.
* Export CSV/JSON non-empty.

---

## 12) Example Payloads

**Create team (request)**

```json
{
  "team_name": "Bag Bandits",
  "players": [{"name": "A. Player"}, {"name": "B. Player"}],
  "captain_contact": "a.player@example.com"
}
```

**Create team (response)**

```json
{ "ok": true, "data": { "teamId": "tm_8G3K", "team_code": "K7M2Q9" } }
```

**Score submit**

```json
{ "score": { "a": 21, "b": 15 } }
```

**Bracket item (GET /bracket excerpt)**

```json
{
  "matches": [
    {
      "matchId": "m_r1_00",
      "round": 1,
      "index": 0,
      "teamA": {"teamId": "tm_1", "name": "Bag Bandits"},
      "teamB": {"teamId": "tm_2", "name": "Corn Stars"},
      "court": "Court 1",
      "start_slot": "2025-09-18T14:00:00-04:00",
      "status": "scheduled",
      "score": {"a": 0, "b": 0},
      "next_match_id": "m_r2_00",
      "next_slot": "A"
    }
  ]
}
```

---

## 13) Configuration Defaults

* `match_duration_min`: **20** (configurable)
* `num_courts`: **4**
* Timezone: **America/Toronto**
* Poll interval: **10–15s** (client)
* Team size: **2 + optional sub**

---

## 14) Operational Playbook (day-of)

* T-60: open registration (`state=open`).
* T-15: lock registration → seed → build → assign courts.
* Print exports: bracket PDF, schedule CSV; pin one big “Now/Next” screen.
* Scorekeepers use PIN-gated page; one device per court preferred.

---

## 15) Extension Hooks (post-MVP)

* Double-elimination switch (winners/losers bracket schema).
* SMS alerts (SNS) to captains: “Report to Court X”.
* Per-team page with results history & simple ELO.
* Cognito user pools if you later want accounts.

