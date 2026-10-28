# AI use and prompt history

This project was developed with AI assistance in Codex. The original project prompt is preserved verbatim in [`original-master-prompt.txt`](original-master-prompt.txt); it specified the requested product, stack, schemas, business rules, generator, validation, interface, and delivery expectations.

## Follow-up prompt history

After the master prompt, the project-specific follow-ups in the conversation were:

1. “create a repo in the github and push the code to that with a clean readme file”
2. “demo account is login failed to fetch”
3. “for every thing it is showing the same screen and also the production site dropdoen is also not woking”

The second prompt led to correcting the allowed browser origin. The third led to API-backed content for each navigation section and a working site selector. Earlier questions about the database, test stack, and project location were clarification requests rather than implementation instructions.

## Where AI assisted

AI drafted the initial application structure, SQLAlchemy models, FastAPI routes and services, deterministic synthetic generator, validator, React dashboard and section views, migration setup, and project documentation. AI also diagnosed the browser CORS failure and the nonfunctional navigation and site selector, then revised those areas.

## Checks recorded during development

- Python source compilation succeeded.
- The three current pytest unit tests passed.
- The starter generator produced 40 assets, 100 calibration events, and 1,000 production uses.
- The starter export validator detected all four labeled injected anomaly scenarios and reported no primary-key or foreign-key violations.
- The React/TypeScript production build succeeded.
- Local smoke checks confirmed demo login, API health, dashboard data, and the API collections used by the interface.

These checks were run with AI assistance. They are not a substitute for independent candidate review, and the project does not yet have API integration or browser end-to-end tests.

## Candidate review to complete before submission

Do not claim personal review or changes that you did not perform. Replace the prompts below with your own accurate account after reviewing the implementation:

- I personally reviewed these files, business rules, or design decisions: **[complete]**
- I changed or challenged these AI-generated choices: **[complete, or state none]**
- I independently ran these checks and observed these results: **[complete]**
- The main trade-off I would explain in a walkthrough is: **[complete]**

The README documents current limitations, including the simplified UI workflows, demo site-to-location mapping, local demo credentials, and absence of production OT control.
