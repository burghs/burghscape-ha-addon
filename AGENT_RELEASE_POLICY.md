# Agent Release Policy

The supported Burghscape Agent is an independent Home Assistant add-on. Its authoritative source is the `main` branch and its version is declared in `burghscape_agent/config.yaml`.

Agent `0.2.57` is the current compatible read-only user-inventory release. It retains all 0.2.56 reporting and backup behavior, advertises `ha_users_read`, and processes inventory requests through a worker isolated from heartbeat/reporting. It remains independently versioned from Platform RC1.4.3. Home Assistant updates only the Agent container; they never deploy the Platform. Existing installations update normally and do not require reinstalling the add-on or replacing the subscription token.

Agent releases require a tested Agent change, a semantic `0.2.x` version bump, matching Agent changelog/docs, a commit to `main`, and Home Assistant repository refresh/update validation. Platform-only releases must not bump the Agent.

The legacy `/home/kenny/burghscape/ha-add-on` directory is not a supported release source and its `0.1.0` metadata must not be used for installs.
