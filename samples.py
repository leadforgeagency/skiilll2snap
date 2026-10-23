"""Demo extractions — what Gemma returns for a good snap. Use if the venue Wi-Fi dies:
the builder + validator + zip still demo perfectly, and these are labelled as samples."""

SAMPLE_EXTRACTIONS = {
    "☕ Whiteboard photo — Pour-over coffee SOP (cafe training board)": {
        "skill_name": "pour-over-coffee",
        "title": "Pour-Over Coffee (Cafe Standard)",
        "description": "Brew a pour-over coffee to the cafe's house standard. Use when a barista, trainee, or home brewer wants this cafe's exact method, ratios, and timings rather than a generic recipe.",
        "when_to_use": ["A trainee asks how to make a pour-over", "Brewing a V60 for a customer"],
        "prerequisites": ["V60 dripper and filter", "Gooseneck kettle", "Scale and timer", "Fresh coffee beans and grinder"],
        "inputs": ["Cup size / amount of coffee to brew"],
        "steps": [
            "Weigh 15g of coffee and grind medium-fine, like sea sand (board note).",
            "Rinse the paper filter with hot water and discard the rinse water.",
            "Add the grounds, start the timer, and bloom with 45g of water for 30 seconds.",
            "Pour in slow circles up to 150g by 1:00, then up to 250g total by 1:30.",
            "Let it draw down fully — total brew time should be 2:30 to 3:00. Serve immediately.",
        ],
        "tools": ["V60 dripper", "gooseneck kettle", "scale", "timer"],
        "constraints": ["Water at 92-94°C — never boiling, it burns the coffee (underlined twice on the board).",
                      "If total time passes 3:00, grind coarser next time; under 2:30, grind finer."],
        "examples": [{"input": "Make me a pour-over", "output": "A 250g cup brewed in about 2:45 using the 15g / 1:16 ratio above."}],
        "unclear_items": [],
        "evidence": "photo of a cafe whiteboard titled 'POUR OVER — HOUSE METHOD' with ratio and timings",
    },
    "🔧 Screenshot — Git release checklist (team wiki)": {
        "skill_name": "release-a-version",
        "title": "Release a New Version (Team Checklist)",
        "description": "Run this team's release process end to end. Use when a developer is asked to ship, release, or tag a new version of the project and must follow the team's exact checks instead of improvising.",
        "when_to_use": ["Releasing or tagging a new version", "A user asks 'ship it' / 'do a release'"],
        "prerequisites": ["Clean git working tree", "CI access", "Changelog file in the repo root"],
        "inputs": ["New version number (semver)"],
        "steps": [
            "Run the full test suite locally and confirm it is green.",
            "Update CHANGELOG.md with the new version and today's date.",
            "Bump the version in the package manifest — do not edit it anywhere else.",
            "Commit as 'release: vX.Y.Z', tag vX.Y.Z, and push the tag.",
            "Watch the CI release job until the artefacts are published, then post the changelog in the team channel.",
        ],
        "tools": ["git", "CI dashboard"],
        "constraints": ["Never release with failing tests — stop and report instead.",
                        "Never force-push a release tag that is already published."],
        "examples": [{"input": "Release version 1.4.0", "output": "Tag v1.4.0 pushed, CI artefacts published, changelog posted to the team channel."}],
        "unclear_items": ["The wiki screenshot does not show who approves a release — flagged, not invented."],
        "evidence": "screenshot of a team wiki page titled 'Release checklist'",
    },
}
