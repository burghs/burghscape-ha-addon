# Getting Started visuals

This inventory tracks the temporary instructional visuals used by the authenticated
Getting Started guide. They are original HTML/CSS interface illustrations, not live
screenshots. Critical instructions remain in the surrounding text.

## Visual inventory

| Stage | Purpose | Format | Accessible description/caption | Temporary | Real screenshot later |
|---|---|---|---|---|---|
| Welcome | Recognize the Client Portal sign-in flow | HTML/CSS mock interface | Example Client Portal sign-in with email, password, and Sign in | Yes | Yes |
| Create HA Token | Find Home Assistant Security and create a long-lived token | HTML/CSS mock interface | Example Security screen with token name and Create token | Yes | Yes |
| Subscription Token | Find the masked Burghscape token and safe controls | HTML/CSS mock interface | Example Burghscape Details card with masked token and Show/Copy | Yes | Yes |
| Install Agent | Add the repository and install Burghscape Agent | HTML/CSS mock interface | Example Apps view with repository, Agent listing, and Install | Yes | Yes |
| Configure Agent | Recognize required Agent fields and monitoring options | HTML/CSS mock interface | Example configuration with platform, subscription, HA token, and Save | Yes | Yes |
| Start Agent | Enable startup, start the Agent, and recognize successful logs | HTML/CSS mock interface | Example Agent screen with Start on boot, Start, and successful status rows | Yes | Yes |
| Remote Access | Distinguish the Remote URL from the Client Portal | HTML/CSS mock interface | Example remote Home Assistant view showing a secure online connection | Yes | Yes |
| Android | Enter the Remote URL and understand Android permission prompts | HTML/CSS mock interface | Example Android setup with server address, Location, and Nearby devices | Yes | Yes |
| iPhone/iPad | Enter the Remote URL and understand staged iOS permissions | HTML/CSS mock interface | Example iOS setup with server address and location choices | Yes | Yes |

## Replacement rules

When validated screenshots become available, replace one visual at a time. Crop all
secrets, email addresses, client names, tokens, hostnames, and device identifiers.
Keep the current captions, responsive container, written instructions, and accessible
description unless the validated workflow changes. Screenshots must be optimized,
lazy-loaded, and checked in light and dark themes.

## Audit record

- Ten stages: Welcome, HA Token, Subscription Token, Install Agent, Configure Agent,
  Start Agent, Remote Access, Android, iPhone/iPad, Finish.
- Nine previous filename-driven image slots had no corresponding assets and displayed
  placeholder copy.
- The previous mobile stage list was a tall single-column region.
- Long numbered lists used inside markers and cramped wrapped lines.
- Previous/Next controls followed long articles and were easy to lose below the fold.
- Stage headings were oversized at narrow widths.
- Token/URL control rows could become cramped.
- Code and table contracts already used internal overflow; these are retained.
- The guide uses dark design tokens and includes reduced-motion handling.

## Manual acceptance status

Automated structure and route validation do not replace visual acceptance. Keep
Getting Started **IN PROGRESS** until the desktop, tablet, iPhone, Android, landscape,
and Home Assistant webview checklist in `LAUNCH_STATUS.md` has been signed off.
