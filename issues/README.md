# TurnrCogs/issues
Create and view your GitHub issues

## Installation
`[p]repo add Turnr https://github.com/TurnrDev/TurnrCogs`
`[p]cog install Turnr isssues`

## Usage
1. Set your [GitHub Access Token](https://github.com/settings/tokens) with `[p]issueset token <token>`
2. Set your repo with `[p]issueset repo <User/Repo>`
3. Configure your labels for `[p]bug`, `[p]enhancement`, and `[p]feature` with the respective setting on `[p]issueset <bug/enhancement/feature> <label>` (defaults are `"bug_label": "bug"`, `"feature_label": "enhancement"`, `"enhancement_label": "enhancement"`)
4. Configure your labels for each priority level with `[p]issueset priority <level> <label>` (defaults are `{"1": "low", "2": "medium", "3": "high"}`)
5. Configure your default priority level with `[p]issueset default_priority <level>` (default is `2`)
