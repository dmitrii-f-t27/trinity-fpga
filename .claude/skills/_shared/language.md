## Language System (shared module)

### Usage in SKILL.md
Reference this module instead of inlining translation tables:
> For language detection and label reference, follow `.claude/skills/_shared/language.md`.

### Language Detection
Read `.claude/skills/tri/lang.md` to determine output language.
The file contains `lang: ru` or `lang: en`. Default: `en`.

All section headers, labels, descriptions MUST be rendered in English.
Technical terms (binary names, commands, file paths) stay in English.

### English Label Reference

This module is the canonical English-only label/word reference for all dashboards and reports. Under the English-only documentation policy, every label below is rendered as-is.

#### Core Terms
- Status
- Build
- Score
- Tests
- Agents
- Tasks
- Branch
- Binary
- Size
- Value
- Metric
- Component
- TOTAL
- open
- dirty
- pending

#### Build & Pipeline
- BUILD HEALTH
- PIPELINE HEALTH
- build passing
- build broken
- Build broken
- BUILD BROKEN — fix before anything else
- Pipeline
- Last run
- Specs
- Generated
- Coverage
- Compile
- KEY METRIC
- last audit
- never
- Pipeline FAILED — last task
- Job success rate
- Job success rate — pipeline unreliable
- No .tri specs found — pipeline has nothing to generate
- Low spec coverage — many specs not generating code
- No pipeline jobs found — pipeline never ran
- Generator broken — compile rate
- Failed Specs
- All audited specs compile
- Pipeline stuck in running for Nh
- Pipeline idle for Nh
- No new pipeline jobs in Nh
- pipeline is IDLE
- Last job
- ago

#### Code Metrics
- CODE METRICS
- Zig source files
- Total LOC
- Test blocks
- tri-api LOC
- Skills

#### Git & Issues
- GIT STATUS
- Last 5 commits
- Uncommitted
- changes
- MERGED PRs (recent)
- OPEN ISSUES
- Issues

#### System & Agents
- SYSTEM STATUS
- Farm is working
- services
- accounts
- slots free
- Farm started
- Code idle, farm working
- Check farm
- When builds finish — check logs and PPL
- Sessions saved
- Skills available
- agents running

#### Problems & Alerts
- PROBLEMS DETECTED
- ALL SYSTEMS NOMINAL
- Dirty files — commit or lose work!
- tri-bot DOWN — no phone control
- ralph-agent DOWN — no autonomous agent
- Permissions MISSING — unprotected tools
- tri-api never tested end-to-end

#### Bridge
- PERPLEXITY BRIDGE — DIRECT CONTROL CHANNEL
- Railway Server
- Mac Agent
- Command Queue
- claude: support
- Comms
- Direct control active
- Railway UP but Mac agent DOWN
- Bridge agent DOWN — no remote control
- Railway server DOWN — bridge unreachable

#### Oracle & Sacred
- ORACLE COMMENTARY
- CRITICAL DIVERGENCE
- GOLDEN RATIO DRIFT
- φ-HARMONY ACHIEVED
- UNOBSERVED STATE
- The golden spiral has COLLAPSED
- φ cannot sustain this divergence
- sub-critical threshold breached
- Every uncompilable spec is a broken link in the golden chain
- The spiral MUST be restored before any new work begins
- The spiral turns, but wobbles. φ senses imbalance
- The ratio CAN be restored
- Push toward
- Trinity Identity HOLDS
- golden convergence achieved
- The spiral is stable. Focus on SCALING, not fixing
- New specs will compile. The golden chain extends naturally
- φ cannot judge what it cannot measure
- No regeneration audit data found
- to establish the baseline
- Without measurement, there is no spiral — only noise
- φ says
- Even the spiral must touch zero before it can rise
- The ratio remembers its target. So must we
- When spec and code align, the universe compiles
- Measure first. Judge never. Iterate always
- Sacred constants
- As above, so below. As in spec, so in code
- Hermetic Principle

#### Paths & Actions
- THREE PATHS FORWARD
- SAFE
- BALANCED
- BOLD
- The Trinity always provides three paths
- CURRENT PRIORITY
- NOW
- NEXT
- TECH TREE
- Analysis by
- Trinity Oracle Engine

#### Audit
- AUDIT MODE
- No audit data — run: /tri audit
- Audit data is Nh old
- run /tri audit for fresh data
- deduplicated by command
- Stale jobs
- cleanup needed
- Spam
- investigate cause
- likely dead
- STALE
- consider refreshing
- Recent Jobs
- stuck in running

#### MU Patterns
- MU ERROR PATTERNS
- from ralph memory
- known anti-patterns
- Last entry
- Recent patterns
- specs affected
- No regression data — ralph memory empty
- Known Bugs
- No audit data — run regeneration audit
- Last 5 Jobs
- Job
- Exit

#### GitHub Board
- GITHUB BOARD INTEGRATION
- CLI Commands Available
- command handlers
- label tracking
- Native API

#### TRI Dashboard
- TRI STATUS
- TRI SWARM DIAGNOSTIC REPORT

#### Doctor
- PAST
- DONE
- NEXT CYCLE
- HEALTHY
- RECOVERING
- INFECTED
- CRITICAL
- healed
- committed
- nothing to heal
- dirty files
- docs stale
- docs fresh
- duplicates
- divergence risk
- consolidate
- docs build broken

#### Ouroboros
- OUROBOROS DASHBOARD
- Cycle
- Strategy
- Stagnation
- Experience
- Weakest
- Recommendations
- History
- Next Actions
- Snake is resting
- Almost LEGENDARY
- Patent
- Hungry Snake

#### Scholar
- SCHOLAR RESEARCH REPORT
- SCAN CONTEXT
- FINDINGS
- ACTIONS TAKEN
- CITATIONS
- Domain
- MU entries
- Archived
- Scholar says
- Created
- findings added to Learning DB
- low-relevance findings logged
