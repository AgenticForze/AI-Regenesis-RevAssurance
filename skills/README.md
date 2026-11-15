# Runtime skills

Each folder is one investigation procedure the agent can load. `SKILL.md` front matter says
when to use it (`root_causes`) and which tools it may call (`tools`); the body is the procedure.
The agent loads the body only for the case in hand (see `src/ra/skills.py`).

To add a skill: create `skills/<name>/SKILL.md`, list only tools that exist in
`src/ra/tools/`, and add a test case to `tests/test_skills.py`. These are product skills;
the Claude Code skills used to build the product live in `.claude/skills/`.
