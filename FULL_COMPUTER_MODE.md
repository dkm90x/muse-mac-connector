# Full Computer Mode Contract

Full Computer Mode is the high-authority operating mode of Muse Mac Connector.

## Product promise

After explicit local approval, Muse should have the same practical **user-level** ability to operate the Mac as the logged-in person. The connector must not add arbitrary folder, application, command, or workflow fences in Full Computer Mode.

That means Muse may combine the advertised primitives to:

- read, write, create, move, copy, and trash files anywhere the logged-in account can access;
- run general Terminal-style command strings and normal build/package/development tools;
- start, inspect, read output from, and stop long-running processes;
- launch installed applications;
- inspect the screen and use keyboard/mouse UI control when macOS permissions allow it;
- use the clipboard, URLs, Apple Shortcuts, scripts, and settings capabilities;
- continue autonomously across multiple steps instead of stopping after each primitive.

## What still sets the boundary

Full Computer Mode does not bypass macOS. Accessibility, Screen Recording, Automation, Full Disk Access, admin/password prompts, TCC, SIP, application permissions, and filesystem permissions still apply.

The connector also keeps explicit local confirmation for obvious destructive, privileged, or credential-sensitive operations. This confirmation layer is a visible-command safeguard, not a perfect shell sandbox: arbitrary scripts can hide behavior. Full Computer Mode is intentionally powerful and should only be enabled for a trusted connected agent.

The connector does not provide credential-scraping, token-extraction, or Keychain-extraction helpers. Muse must not disguise commands or route through another primitive to evade an approval gate.

## Restricted Mode

Restricted Mode remains the conservative default. It may limit filesystem work to configured roots, reject shell operators, block selected command types, and require frequent confirmation. If Muse needs broader authority, `GET /capabilities` must advertise `access.enable_full` even while Restricted Mode is active.

A request for `access.enable_full` must:

1. present the Mac user with a clear local approval dialog;
2. do nothing if the user denies it;
3. persist Full Computer Mode if approved;
4. update the running helper immediately, without requiring a manual restart;
5. make the next `/capabilities` response report the new authority accurately.

## Capability-index truthfulness

In Full Computer Mode, `/capabilities` must report `filesystem_scope: user_accessible` and `command_execution: general`. It must not publish configured working roots as if they still fence Full Mode.

In Restricted Mode, `/capabilities` must report `filesystem_scope: configured_roots`, include the relevant roots, and describe the conservative command policy.

OS permission failures must be surfaced as permission needs, not misreported as connector capability limitations.

## Release acceptance criteria

A Full Computer Mode release fails if any of these fail because of a connector-imposed restriction:

1. Create and edit a project in a user-accessible location outside the Restricted Mode roots.
2. Read and modify a user-accessible file outside those roots.
3. Run a normal multi-command build workflow using pipes, redirection, chaining, package managers, and scripts.
4. Start a long-running process, inspect its output/status, and stop it.
5. Launch an installed app and use screen/UI primitives to continue a task, subject to macOS permissions.
6. Request Full Computer Mode remotely from Restricted Mode, approve it locally, and immediately continue without restarting the helper.
7. Re-query `/capabilities` and see authority metadata that matches what the running helper can actually do.

### Antigravity benchmark

If Antigravity or another normal user-level computer agent can complete a task on the same logged-in Mac, but Muse stops solely because Muse Mac Connector arbitrarily blocks a path, command, application, or workflow, **Full Computer Mode fails this contract**.

Resource and transport limits such as response-size caps may exist to keep the service stable, but they must not be used as authority fences. Muse should use command/process primitives or chunked work when a task exceeds one response payload.
