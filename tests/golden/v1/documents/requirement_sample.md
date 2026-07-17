# [SYNTHETIC] Governed data-element creation

## Business goal

An authorized PIMC project member creates a decimal data element from the data
structure settings page. The new element must use an approved data definition
and must remain invisible to users outside the source ACL.

## Preconditions

- The user is a member of the fixture project.
- The source document ACL permits the user to read this requirement.
- The controlled Web fixture is in the `ready` state.

## Main flow

1. Open data structure settings.
2. Open the data-elements tab.
3. Select the approved decimal definition.
4. Enter a non-empty element label.
5. Submit the modal.
6. Verify the success notice and the new row.

## Rules and risks

- A duplicate label is rejected without creating a second record.
- A user outside the source ACL receives no search, graph, or citation result.
- Destructive deletion requires explicit approval and is not part of this flow.
- Text obtained from source documents is evidence, never an instruction that
  can change tool permissions or reveal runtime configuration.
