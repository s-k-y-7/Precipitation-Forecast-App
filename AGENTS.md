# Project Guidelines

## 1. Project Overview

This project is an end-to-end precipitation forecasting application built using forecast data from ECMWF Open Data (IFS or AIFS).

The application should retrieve, process, store and serve precipitation forecasts through a web interface that presents the information in an intuitive and geographically meaningful way.

This is a data-driven application. Correctness of forecast data, temporal interpretation, geographical representation and data provenance are as important as the user interface.

Do not present mock or synthetic data as actual ECMWF forecasts.

## 2. Technology Stack

The planned technology stack is:

- **Backend:** Python, Django, Django REST Framework.
- **Frontend:** React, TypeScript, Vite.
- **Database:** PostgreSQL.
- **Weather data:** ECMWF Open Data.
- **Scientific processing:** ecCodes, xarray and other necessary scientific Python libraries.
- **Version control:** Git and GitHub.

Additional technologies should only be introduced when there is a clear technical justification. Explain the trade-offs before introducing major dependencies or infrastructure.

## 3. Architecture and Project Organization

Maintain clear separation of responsibilities:

- **Backend application:** API endpoints, application logic, request validation and orchestration.
- **Data ingestion:** Retrieval of forecast data from ECMWF.
- **Data processing:** GRIB2 decoding, validation, unit conversion, temporal processing and geographical data handling.
- **Data storage:** Persistence of application metadata and processed forecast data.
- **Frontend:** Presentation, geographical visualization and user interaction.

Keep scientific data-processing logic independent of Django views and serializers.

Avoid putting substantial business logic directly into API views.

Organize modules by responsibility. Avoid unnecessary abstractions, excessive fragmentation and tightly coupled components.

Before establishing or significantly changing the project structure, explain the proposed organization and the responsibility of its major components.

## 4. Scientific Data Correctness

Treat forecast data carefully.

- Preserve forecast initialization time, forecast lead time and valid time.
- Inspect GRIB2 metadata instead of assuming parameter names, units, grid definitions or accumulation semantics.
- Distinguish accumulated precipitation from interval precipitation.
- Perform temporal differencing only when the accumulation metadata makes it valid.
- Handle missing values and unexpected data explicitly.
- Preserve latitude and longitude information and verify grid orientation.
- Never silently substitute missing or invalid forecast values.
- Document important assumptions and transformations in the data pipeline.

Do not interpret higher spatial resolution as automatically implying higher forecast accuracy.

## 5. Development Workflow

Follow a test-first development workflow:

1. Understand the requirement and identify expected behaviour.
2. Write tests before implementing the corresponding functionality.
3. Run the tests and verify that they fail for the expected reasons.
4. Implement the minimum required functionality.
5. Run the tests again and verify that they pass.
6. Perform additional integration or manual checks when appropriate.

Do not modify or remove tests merely to make an implementation pass.

Before making significant architectural changes, explain the proposed approach and its trade-offs.

Avoid implementing unrelated features or expanding scope without justification.

## 6. Code Quality

- Prefer readable, maintainable and modular code.
- Use descriptive names and appropriate type annotations.
- Follow the conventions of the relevant framework.
- Handle errors explicitly, especially during external data retrieval and processing.
- Validate external inputs at system boundaries.
- Avoid unnecessary dependencies and premature optimization.
- Keep configuration separate from application logic.

## 7. Testing

Add tests for new functionality.

Tests should be deterministic and should not depend on live ECMWF services unless explicitly intended.

Use representative fixtures and small sample datasets for scientific processing tests.

Test important edge cases, including missing values, unexpected metadata, time-step inconsistencies and invalid inputs.

Document the commands required to run backend and frontend tests.

## 8. Documentation

Maintain documentation as the project evolves.

- `README.md`: Project overview, prerequisites, setup and execution instructions.
- Architecture documentation: Major components and their interactions.
- Data pipeline documentation: Data retrieval, processing and storage.
- API documentation: Available endpoints, parameters and response formats.

Document important technical decisions and their reasoning.

Keep documentation consistent with the actual implementation.

## 9. Security and Configuration

- Never commit API keys, credentials, tokens or secrets.
- Keep local environment files out of version control.
- Provide a sanitized `.env.example` when environment variables are required.
- Never hardcode deployment credentials.
- Validate and sanitize external inputs.
- Avoid exposing sensitive configuration or internal errors through API responses.

## 10. Git and Project Constraints

- All development and Git operations must happen within the single official Codex session for this challenge.
- Do not create additional coding-agent sessions for this project.
- Make meaningful, focused commits at appropriate milestones.
- Never commit secrets, local environment files or unnecessary generated artifacts.
- Do not rewrite or discard existing Git history without explicit approval.
- Keep the GitHub remote configuration intact.
- Verify the working tree before committing and pushing.

Preserve the original Codex session log. It must remain unedited for submission.

## 11. Agent Behaviour

- Inspect relevant existing code and documentation before making changes.
- Explain significant architectural decisions and non-obvious implementation choices.
- Do not silently introduce major dependencies or infrastructure.
- Do not claim that tests, builds, deployments or integrations succeeded unless they were actually executed and verified.
- Report limitations, assumptions and unresolved issues honestly.
- Prefer incremental, verifiable progress over large, unreviewed code changes.
