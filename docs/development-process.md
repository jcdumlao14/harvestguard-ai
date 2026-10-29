# Development Process

## Specification first

Review the product specification and acceptance criteria before coding.
Create one public GitHub Issue per coherent unit of work.

## Branching

Use a short-lived branch per Issue, for example:
`feat/HG-01-inventory-crud`

Do not commit directly to the production branch. Use pull requests and inspect
the diff before merging.

## Issue workflow

1. Confirm acceptance criteria and dependencies.
2. Create a task plan.
3. Implement a bounded change.
4. Add regression and relevant automated tests.
5. Run checks locally.
6. Request independent review.
7. Link evidence and close the Issue only after verification.

## AI-assisted work

Record which tool or agent helped, what task it performed, and what verification
a human or independent test performed. AI output is a proposal, not evidence.

## Release workflow

Pull request -> CI -> review -> merge -> development deployment -> smoke tests
-> manual production approval -> production smoke tests.

If verification fails, stop promotion and use the documented rollback process.
