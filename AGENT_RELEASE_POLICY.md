# Agent Release Policy

The supported Burghscape Agent is an independent Home Assistant add-on. Its authoritative source is the `main` branch and its version is declared in `burghscape_agent/config.yaml`.

Agent `0.2.55` is valid and should remain published: it corrects native Home Assistant backup telemetry. It is unrelated to Platform RC1.4.3 by design. Home Assistant updates only the Agent container; they never deploy the Platform.

Agent releases require a tested Agent change, a semantic `0.2.x` version bump, matching Agent changelog/docs, a commit to `main`, and Home Assistant repository refresh/update validation. Platform-only releases must not bump the Agent.

The legacy `/home/kenny/burghscape/ha-add-on` directory is not a supported release source and its `0.1.0` metadata must not be used for installs.
