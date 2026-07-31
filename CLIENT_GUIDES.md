# Client Guides & Help

Client Guides is a reusable, Platform-only publishing module for protected visual instructions. Management administrators open **Client Guides**, upload a PNG, JPEG, WebP, or PDF, set title/description/category/order/featured status, choose all-client or explicit selected-client visibility, preview it, and publish or unpublish it. Files may be replaced atomically and guides may be permanently deleted with confirmation.

Client portal users open **Guides & Help**. Only published guides visible to their authenticated tenant are listed. Image and PDF previews and downloads repeat the same authorization check; responses never expose the server storage name or path. Images open in a scrollable full-size viewer suitable for long portrait instructions. PDFs use the browser viewer with a separate download action.

Uploads are signature-checked, limited by `GUIDE_MAX_UPLOAD_BYTES` (20 MiB by default), assigned random storage names, and stored under `GUIDE_MEDIA_ROOT` (`/guide-media`). Production mounts `/home/kenny/guides/client-guides` there, so uploads survive backend recreation. That directory and the `client_guides` / `client_guide_assignments` tables are included in normal host and PostgreSQL backup expectations. Restoring a complete guide library requires both the database and guide-media directory.

Visibility is explicit: `all` ignores assignments; `selected` requires at least one valid client assignment. Client deletion cascades only its assignments. Guide deletion cascades assignments and removes the managed file; replacement removes the superseded file after the new database state commits.

The existing first-login tour includes Guides & Help. Existing completed onboarding records are not reset. A separate dismissible `mybeacon-guides-spotlight-v1` browser-local spotlight introduces the feature once per browser. Guide New badges are also browser-local (`mybeacon-guide-seen-v1`), so acknowledgement does not synchronize between browsers or devices. Any spotlight/API failure is caught and cannot block portal access.

Management endpoints require `get_current_admin`. Client endpoints require an active `portal_token` and tenant visibility. Uploads reject unsupported, oversized, malformed, and traversal-capable names. Audit events cover creation, metadata/publish changes, file replacement, and deletion.

Tests cover authentication, supported and rejected files, size/signature validation, all/selected visibility, unpublished hiding, cross-client file denial, atomic replacement cleanup, deletion/cascades, management UI, viewers, conditional featured content, and onboarding/spotlight contracts. The full existing Platform regression suite remains mandatory before deployment.

Rollback uses the standard deployment script with the prior Platform commit. The additive tables and media directory may remain unused; do not delete them during rollback. This preserves guide data for re-deployment and avoids destructive rollback.
